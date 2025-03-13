import datetime
import json
import time
import requests
import xhs.help
from xhs import XhsClient

class XhsSignClient:
    def __init__(self, sign_server_url="http://localhost:5005"):
        self.sign_server_url = sign_server_url
        self.cookies = self.get_cookies()
        
    def get_cookies(self):
        try:
            response = requests.get(f"{self.sign_server_url}/cookies")
            if response.status_code == 200:
                return response.json()
            return {"a1": "", "web_session": ""}
        except Exception as e:
            print(f"获取cookies失败: {str(e)}")
            return {"a1": "", "web_session": ""}
    
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
                elif i < max_retries - 1:  # 如果不是最后一次重试
                    print(f"签名失败，正在重置浏览器并重试...")
                    self.reset_browser()
                    time.sleep(2)  # 等待一下再重试
                else:
                    print(f"签名失败，状态码: {response.status_code}")
                    return None
            except Exception as e:
                print(f"签名请求异常: {str(e)}")
                if i < max_retries - 1:  # 如果不是最后一次重试
                    print("正在重置浏览器并重试...")
                    self.reset_browser()
                    time.sleep(2)  # 等待一下再重试
                else:
                    return None

if __name__ == '__main__':
    # 创建签名客户端
    sign_client = XhsSignClient()
    xhs_client = XhsClient(cookie=sign_client.cookies, sign=sign_client.sign)
    
    try:
        # 获取笔记信息
        note_info = xhs_client.get_note_by_keyword("猫")
        print("搜索结果:", note_info)
    except Exception as e:
        print(f"获取笔记信息失败: {str(e)}")
        # 如果失败，尝试重置浏览器并重试
        if sign_client.reset_browser():
            try:
                note_info = xhs_client.get_note_by_keyword("猫")
                print("重试搜索结果:", note_info)
            except Exception as e2:
                print(f"重试获取笔记信息失败: {str(e2)}")