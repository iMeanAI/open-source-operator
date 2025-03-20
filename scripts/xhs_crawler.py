import time
import re
import json
import pprint
import os
import requests
from xhs import XhsClient
from xhs.core import SearchNoteType
from xhs.exception import ErrorEnum, DataFetchError, IPBlockError

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



# helper function to get note ids from the original reponse
def get_id_from_response(note_info: dict, note_nums: int = 10):
    note_items = note_info["items"][:note_nums]
    note_ids_xsec = [[item["id"],item["xsec_token"]] if item["id"] else None for item in note_items]
    return note_ids_xsec


# save note info to local
def save_note_info(note_info: dict, save_dir: str):
    pprint.pprint(note_info)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    title = note_info.get('title', '无标题')
    desc = note_info.get('desc', '无描述')
    
    note_dir = os.path.join(save_dir, "".join(x for x in title if x.isalnum() or x in (' ','-','_')))
    if not os.path.exists(note_dir):
        os.makedirs(note_dir)
        
    with open(os.path.join(note_dir, 'info.txt'), 'w', encoding='utf-8') as f:
        f.write(f'标题: {title}\n\n')
        f.write(f'描述: {desc}\n\n')
        
        comments = note_info.get('comments', [])
        if comments:
            f.write('热门评论:\n')
            # 按点赞数排序并获取前10条
            sorted_comments = sorted(comments, key=lambda x: x.get('like_count', 0), reverse=True)[:10]
            for idx, comment in enumerate(sorted_comments, 1):
                content = comment.get('content', '')
                like_count = comment.get('like_count', 0)
                f.write(f'{idx}. {content} (点赞数:{like_count})\n')
                
    # 下载图片
    if 'image_list' in note_info:
        img_dir = os.path.join(note_dir, 'images')
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)
            
        for idx, img in enumerate(note_info['image_list']):
            img_url = img['info_list'][0].get('url', '')
            if img_url:
                try:
                    img_resp = requests.get(img_url, timeout=10)
                    if img_resp.status_code == 200:
                        img_path = os.path.join(img_dir, f'img_{idx+1}.jpg')
                        with open(img_path, 'wb') as f:
                            f.write(img_resp.content)
                except Exception as e:
                    print(f'下载图片失败: {str(e)}')
                    
    return note_dir


# 保存完整的笔记信息到JSON文件
def save_note_to_json(note_info: dict, save_dir: str, filename: str = None):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # 如果没有提供文件名，使用笔记标题作为文件名
    if filename is None:
        title = note_info.get('title', '无标题')
        filename = "".join(x for x in title if x.isalnum() or x in (' ','-','_'))
        
    # 确保文件名有.json后缀
    if not filename.endswith('.json'):
        filename += '.json'
    
    file_path = os.path.join(save_dir, filename)
    
    # 以格式化的方式写入JSON文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(note_info, f, ensure_ascii=False, indent=4)
    
    print(f"笔记信息已保存到: {file_path}")
    return file_path


#save note info searched by keyword to local
def save_note_info_by_keyword(keyword: str, save_dir: str):
    sign_client = XhsSignClient()
    xhs_client = XhsClient(cookie=sign_client.cookies_str, sign=sign_client.sign)
    # only search image or text note and ignore videos
    try:
        note_info = xhs_client.get_note_by_keyword(keyword, note_type=SearchNoteType.ALL)
    except Exception as e:
        print(f"获取笔记信息失败: {str(e)}")
        if sign_client.reset_browser():
            try:
                note_info = xhs_client.get_note_by_keyword(keyword, note_type=SearchNoteType.IMAGE)
            except Exception as e2:
                print(f"重试获取笔记信息失败: {str(e2)}")

    note_ids_xsec = get_id_from_response(note_info,3)

    if note_ids_xsec:
        for id,xsec in note_ids_xsec:
            try:
                note_card = xhs_client.get_note_by_id_from_html(note_id=id, xsec_token=xsec, xsec_source="pc_search")
                save_note_info(note_card, save_dir)
                time.sleep(2)  
            except Exception as e:
                print(f"获取笔记ID {id} 的详情失败: {str(e)}")
    else:
        print("没有找到笔记ID")


if __name__ == '__main__':
    save_dir = "复旦大学"
    save_note_info_by_keyword("复旦大学图片", save_dir)
