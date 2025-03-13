import requests
import json


def jina_crawl():
    url = "https://r.jina.ai/"
    headers = {
        "Authorization": "Bearer jina_xxxx"
    }
    data = {
        "url": "https://www.xiaohongshu.com/search_result?keyword=%25E6%2583%2585%25E7%25B3%25BB%25E6%25AF%258D%25E6%25A0%25A1%25E4%25B8%2583%25E4%25B8%25AD&source=unknown"
    }

    response = requests.post(url, headers=headers, json=data)
    print(response.text)



def jina_requset(prompt):
    url = "https://deepsearch.jina.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "model": False,
        "messages": [
            {
                "role": "user",
                "content": prompt
            },
        ],
        "stream": True,
        "reasoning_effort": False
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(response.text)

if __name__ == "__main__":
    prompt = "在小红书、携程、马蜂窝或者Reddit上搜索,并推荐一些曼哈顿的人均50刀以下的评分高的可以打卡的特色美食"
    jina_requset(prompt=prompt)