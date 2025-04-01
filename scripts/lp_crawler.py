from firecrawl import FirecrawlApp
import re
import pprint
import json
import os

API_KEY = 'fc-b216b25de3464369bed44d239d385d63'
MAX_SEARCH_PAGES = 1
LIMIT = 5
MAX_DEPTH = 1
SEARCH_TYPE = "City"
SORT = "DESC"
RESULT_DIR = "./crawling_results"

def get_lonelyplanet_place_links(app: FirecrawlApp):
    place_links_by_page = {}
    for i in range(MAX_SEARCH_PAGES):
        url = f"https://www.lonelyplanet.com/places?type={SEARCH_TYPE}&sort={SORT}&page={i+1}"

        crawl_result = app.crawl_url(url, params={
            'limit': LIMIT,
            'maxDepth': MAX_DEPTH,
            'scrapeOptions': {
                'formats': ['links'],
            }
        })
        pprint.pprint(crawl_result)

        # 过滤掉搜索页面导航
        if 'data' in crawl_result and len(crawl_result['data']) > 0 and 'links' in crawl_result['data'][0]:
            filtered_links = [link for link in crawl_result['data'][0]['links'][1:] 
                            if not link.startswith("https://www.lonelyplanet.com/places?type=")]
            place_links_by_page[i] = filtered_links

    return place_links_by_page

def save_place_links(place_links_by_page):

    os.makedirs(RESULT_DIR, exist_ok=True)
    
    json_data = []
    for page_index, urls in place_links_by_page.items():
        json_data.append({
            "search_index": page_index,
            "urls": urls
        })
    
    with open(f"{RESULT_DIR}/place_links.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

def save_batch_details(batch_details):
    os.makedirs(RESULT_DIR, exist_ok=True)
    for detail in batch_details:
        with open(f"{RESULT_DIR}/{detail['metadata']['og:title']}.json", "w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=4)

def get_batch_details(app: FirecrawlApp, place_links):
    for index, urls in place_links.items():
        if not isinstance(urls, list):
            urls = [urls]
        print(f"正在获取第 {index+1} 页搜索结果的详细信息...")
        batch_details = app.batch_scrape_urls(urls, params={
                'formats': ['markdown', 'links'],
            }
        )
        pprint.pprint(batch_details) 
        if 'data' in batch_details and len(batch_details['data']) > 0:
            save_batch_details(batch_details['data'])



if __name__ == "__main__":
    app = FirecrawlApp(API_KEY)
    place_links = get_lonelyplanet_place_links(app)
    save_place_links(place_links)

    # 获取每个地点的详细信息
    get_batch_details(app, place_links)