import time
import re
import json
import requests
from xhs import XhsClient
from xhs.core import SearchNoteType
from xhs.exception import ErrorEnum, DataFetchError, IPBlockError

# helper function to get note ids from the original reponse
def get_id_from_response(note_info: dict, note_nums: int = 10):
    note_items = note_info["items"][:note_nums]
    note_ids_xsec = [[item["id"],item["xsec_token"]] if item["id"] else None for item in note_items]
    return note_ids_xsec

# adapted from xhs.core.py
def get_note_by_id_from_html(xhs_client, note_id: str, xsec: str):

    def camel_to_underscore(key):
        return re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()

    def transform_json_keys(json_data):
        data_dict = json.loads(json_data)
        dict_new = {}
        for key, value in data_dict.items():
            new_key = camel_to_underscore(key)
            if not value:
                dict_new[new_key] = value
            elif isinstance(value, dict):
                dict_new[new_key] = transform_json_keys(json.dumps(value))
            elif isinstance(value, list):
                dict_new[new_key] = [
                    transform_json_keys(json.dumps(item))
                    if (item and isinstance(item, dict))
                    else item
                    for item in value
                ]
            else:
                dict_new[new_key] = value
        return dict_new

    url = "https://www.xiaohongshu.com/explore/" + note_id + "?xsec_token=" + xsec + "&xsec_source=pc_search"
    res = xhs_client.session.get(url, headers={"user-agent": xhs_client.user_agent, "referer": "https://www.xiaohongshu.com/"})
    html = res.text
    state = re.findall(r"window.__INITIAL_STATE__=({.*})</script>", html)[0].replace("undefined", '""')
    if state != "{}":
        note_dict = transform_json_keys(state)
        return note_dict["note"]["note_detail_map"][note_id]["note"]
    elif ErrorEnum.IP_BLOCK.value in html:
        raise IPBlockError(ErrorEnum.IP_BLOCK.value)
    raise DataFetchError(html)


class XhsSignClient:
    def __init__(self, sign_server_url="http://localhost:5005"):
        self.sign_server_url = sign_server_url
        self.cookies = self.get_cookies()
        self.cookies_str = self.cookie_dict_to_cookie_str(self.cookies)
        
    def get_cookies(self):
        try:
            response = requests.get(f"{self.sign_server_url}/cookies")
            if response.status_code == 200:
                return response.json()
            return {"a1": "", "web_session": ""}
        except Exception as e:
            print(f"获取cookies失败: {str(e)}")
            return {"a1": "", "web_session": ""}
    
    def cookie_dict_to_cookie_str(self, cookie_dict):
        return ";".join([f"{key}={value}" for key, value in cookie_dict.items()])
    
    def reset_browser(self):
        try:
            response = requests.post(f"{self.sign_server_url}/reset")
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    self.cookies = data["cookies"]
                    return True
            return False
        except Exception as e:
            print(f"重置浏览器失败: {str(e)}")
            return False
    
    def sign(self, uri, data=None, a1="", web_session=""):
        max_retries = 3
        for i in range(max_retries):
            try:
                response = requests.post(
                    f"{self.sign_server_url}/sign",
                    json={
                        "uri": uri,
                        "data": data,
                        "a1": self.cookies["a1"],
                        "web_session": self.cookies["web_session"]
                    }
                )
                if response.status_code == 200:
                    return response.json()
                elif i < max_retries - 1:  
                    print(f"签名失败，正在重置浏览器并重试...")
                    self.reset_browser()
                    time.sleep(2)  
                else:
                    print(f"签名失败，状态码: {response.status_code}")
                    return None
            except Exception as e:
                print(f"签名请求异常: {str(e)}")
                if i < max_retries - 1:  
                    print("正在重置浏览器并重试...")
                    self.reset_browser()
                    time.sleep(2)  
                else:
                    return None

if __name__ == '__main__':
    sign_client = XhsSignClient()
    xhs_client = XhsClient(cookie=sign_client.cookies_str, sign=sign_client.sign)
    
    try:
        note_info = xhs_client.get_note_by_keyword("复旦大学")
        
    except Exception as e:
        print(f"获取笔记信息失败: {str(e)}")
        if sign_client.reset_browser():
            try:
                note_info = xhs_client.get_note_by_keyword("复旦大学",note_type=SearchNoteType.IMAGE)
            except Exception as e2:
                print(f"重试获取笔记信息失败: {str(e2)}")

    note_ids_xsec = get_id_from_response(note_info,3)

    if note_ids_xsec:
        for id,xsec in note_ids_xsec:
            try:
                note_card = get_note_by_id_from_html(xhs_client, id, xsec)
                print(f"笔记ID {id} 的详情:", note_card)
                time.sleep(2)  
            except Exception as e:
                print(f"获取笔记ID {id} 的详情失败: {str(e)}")
    else:
        print("没有找到笔记ID")
