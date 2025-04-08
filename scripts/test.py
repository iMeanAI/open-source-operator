from firecrawl import FirecrawlApp
import re
import pprint
import json
import os
from typing import Optional
API_KEY = ''
MAX_SEARCH_PAGES = 1
LIMIT = 20
MAX_DEPTH = 1
SEARCH_TYPE = "All"
SORT = "DESC"
MAX_CONCURRENT_REQUESTS = 5
RESULT_DIR = "./test_crawling_results"

def save_url_content(url_content: dict, file_name: Optional[str] = None, save_dir: str = RESULT_DIR):
    os.makedirs(save_dir, exist_ok=True)
    url_title = url_content['metadata']['og:title']

    if file_name is None:
        file_name = url_title
    
    with open(f"{save_dir}/{file_name}.json", "w", encoding="utf-8") as f:
        json.dump(url_content, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    app = FirecrawlApp(API_KEY)
    
    # response = app.crawl_url(url='https://www.lonelyplanet.com/usa/san-francisco/attractions',
    #                          params={
    #                              'maxDepth': 2,
    #                              'scrapeOptions': {
    #                                  'formats': ['links'],
    #                                  'waitFor': 5000
    #                              }
    #                          })
    
    # # save_url_content(response, file_name='test_crawling_result')
    # with open(f"{RESULT_DIR}/test_crawling_result.json", "w", encoding="utf-8") as f:
    #     json.dump(response, f, ensure_ascii=False, indent=4)

    response = app.batch_scrape_urls(urls=['https://www.lonelyplanet.com/articles/best-things-to-do-berlin'],
                             params={
                                 'formats': ['links'],
                                 'waitFor': 5000
                             })
    
    with open(f"{RESULT_DIR}/test_scraping_result.json", "w", encoding="utf-8") as f:
        json.dump(response, f, ensure_ascii=False, indent=4)
    
