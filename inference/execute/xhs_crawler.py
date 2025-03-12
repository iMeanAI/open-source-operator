# from xhs_spider.search import Search

# if __name__ == "__main__":
#     search = Search()

#     queries = ["自拍"]
#     for query in queries:

#         number = 2000
#         # 排序方式 general: 综合排序 popularity_descending: 热门排序 time_descending: 最新排序
#         sort = "general"
#         info = {
#             "query": query,
#             "number": number,
#             "sort": sort,
#         }
#         search.main(info)

import datetime
import json

import requests

import xhs.help
from xhs import XhsClient

def sign(uri, data=None, a1="", web_session=""):
    # 填写自己的 flask 签名服务端口地址
    res = requests.post("http://localhost:5005/sign",
    json={"uri": uri, "data": data, "a1": a1, "web_session": web_session})
    signs = res.json()
    return {
    "x-s": signs["x-s"],
    "x-t": signs["x-t"]
}

if __name__ == '__main__':
    cookie = ""
    xhs_client = XhsClient(cookie, sign=sign)
    # get note info
    note_info = xhs_client.get_note_by_keyword("华为手机")