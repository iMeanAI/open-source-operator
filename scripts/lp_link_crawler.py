from firecrawl import FirecrawlApp
import re
import pprint
import json
import os
import time
import logging
from typing import Optional
API_KEY = ''
MIN_SEARCH_PAGES = 1
MAX_SEARCH_PAGES = 1


SEARCH_TYPE = "City"
SORT = "DESC"
MAX_CONCURRENT_REQUESTS = 5
RESULT_DIR = "./crawling_results"
MAX_RETRY = 0  # 最大重试次数

# 确保日志目录存在
os.makedirs(RESULT_DIR, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{RESULT_DIR}/crawler.log", mode='a'),
        logging.StreamHandler()
    ]
)

def filter_links(links: list):
    filtered_links = [link for link in links 
            if (link.startswith("https://www.lonelyplanet.com") and 
                all(excluded not in link for excluded in ["best-in-travel", "login", "?page="]))]
    page_links = [link for link in links 
            if (link.startswith("https://www.lonelyplanet.com") and "?page=" in link)]
    return filtered_links, page_links

def get_url_title(url_content: dict):
    if 'metadata' in url_content and 'title' in url_content['metadata']:
        url_title = url_content['metadata']['title']
    elif 'metadata' in url_content and 'og:title' in url_content['metadata']:   
        url_title = url_content['metadata']['og:title']
    elif 'metadata' in url_content and 'url' in url_content['metadata']:
        url_title = url_content['metadata']['url']
        url_title = url_title.replace("https://www.lonelyplanet.com", "")
        url_title = url_title.replace("/", " ")
    else:
        url_title = url_content['metadata']['scrapeId']
    url_title = url_title.replace("Lonely Planet", "")
    url_title = re.sub(r'[\\/*?:"<>|]', "", url_title)
    url_title = re.sub(r'\s+', " ", url_title)
    url_title = url_title.strip()
    return url_title

def scrape_url_links(app: FirecrawlApp, url: str, print_result: bool = False):
    scrape_result = app.scrape_url(url, params={
        'formats': ['links'],
        'waitFor': 5000
    })
    if print_result:
        pprint.pprint(scrape_result)
    if 'links' in scrape_result:
        filtered_links, page_links = filter_links(scrape_result['links'])
        return filtered_links, page_links
    return [], []

def save_url_links(url_links: list, description: str, file_name: str, save_dir: str = RESULT_DIR, overwrite: bool = False):
    os.makedirs(save_dir, exist_ok=True)
    
    file_path = f"{save_dir}/{file_name}.json"
    
    # 检查文件是否已存在，如果存在则不再保存
    if os.path.exists(file_path) and not overwrite:
        logging.info(f"文件 {file_path} 已存在，跳过保存")
        return
    
    json_data = {
        "description": description,
        "urls": url_links
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

def save_url_content(url_content: dict, file_name: Optional[str] = None, save_dir: str = RESULT_DIR, overwrite: bool = False):
    os.makedirs(save_dir, exist_ok=True)

    if file_name is None:
        file_name = get_url_title(url_content)
    
    file_path = f"{save_dir}/{file_name}.json"
    
    # 检查文件是否已存在，如果存在则不再保存
    if os.path.exists(file_path) and not overwrite:
        logging.info(f"文件 {file_path} 已存在，跳过保存")
        return
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(url_content, f, ensure_ascii=False, indent=4)

def get_batch_url_content(app: FirecrawlApp, url_links: list):
    result = []

    batch_details = app.batch_scrape_urls(url_links, params={
            'formats': ['markdown'],
            'waitFor': 5000
        }
    )
    if 'data' in batch_details and len(batch_details['data']) > 0:  
        result = batch_details['data']
    return result

def get_batch_url_content_with_links(app: FirecrawlApp, url_links: list):
    result = []
    
    batch_details = app.batch_scrape_urls(url_links, params={
            'formats': ['markdown', 'links'],
            'waitFor': 5000
        }
    )

    if 'data' in batch_details and len(batch_details['data']) > 0:
        for data in batch_details['data']:
            if 'links' in data:
                data['links'], _ = filter_links(data['links'])
            result.extend(batch_details['data'])
    return result

def save_failed_urls(failed_urls: list, description: str, save_dir: str):
    """保存爬取失败的URL"""
    os.makedirs(save_dir, exist_ok=True)
    failed_file = f"{save_dir}/failed_urls.json"
    
    existing_data = {}
    if os.path.exists(failed_file):
        with open(failed_file, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = {"failed_urls": {}}
    else:
        existing_data = {"failed_urls": {}}
    
    existing_data["failed_urls"][description] = failed_urls
    
    with open(failed_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
    
    logging.error(f"保存了{len(failed_urls)}个失败的URL到 {failed_file}，描述: {description}")

def scrape_url_links_with_retry(app: FirecrawlApp, url: str, print_result: bool = False, max_retry: int = MAX_RETRY):
    """带重试机制的URL链接抓取"""
    retry_count = 0
    while retry_count <= max_retry:
        try:
            links, page_links = scrape_url_links(app, url, print_result)
            if links and len(links) > 0:
                return links, page_links
            
            logging.warning(f"尝试 {retry_count+1}/{max_retry+1}: URL {url} 返回空链接")
            retry_count += 1
            time.sleep(2)
        except Exception as e:
            logging.error(f"抓取URL链接出错 {url}: {str(e)}")
            retry_count += 1
            time.sleep(2)
    
    logging.error(f"URL {url} 在 {max_retry+1} 次尝试后仍然返回空链接")
    return [], []

def crawl_multi_page_url_links(app: FirecrawlApp, url: str, print_result: bool = False, max_retry: int = MAX_RETRY):
    """带重试机制的多页URL链接爬取"""
    result = []
    failed_urls = []
    try:
        links, page_links = scrape_url_links_with_retry(app, url, print_result, max_retry)
        if links and len(links) > 0:
            result.extend(links)
            for page_link in page_links:
                if '?page=1' in page_link:
                    continue
                links, _ = scrape_url_links_with_retry(app, page_link, print_result, max_retry)
                if links and len(links) > 0:
                    result.extend(links)
                else:
                    logging.warning(f" URL {page_link} 返回空内容")
                    failed_urls.append(page_link)
                    time.sleep(2)
        time.sleep(2)  # 等待2秒
    except Exception as e:
        logging.error(f"爬取URL链接出错 {url}: {str(e)}")
        failed_urls.append(url)
    return result, failed_urls

def get_batch_url_content_with_retry(app: FirecrawlApp, url_links: list):
    """带重试机制的批量URL内容获取"""
    result = []
    failed_urls = []
    url_batches = [url_links[i:i+MAX_CONCURRENT_REQUESTS] for i in range(0, len(url_links), MAX_CONCURRENT_REQUESTS)]
    for url_batch in url_batches:
        try:
            content = get_batch_url_content_with_links(app, url_batch)
            if content and len(content) > 0:
                result.extend(content)
            else:
                logging.warning(f" URL {url_batch} 返回空内容")
                time.sleep(2)
        except Exception as e:
            logging.error(f"获取URL内容出错 {url_batch}: {str(e)}")
            time.sleep(2)
            failed_urls.extend(url_batch)
    
    return result, failed_urls

def main(app: FirecrawlApp):
    # 创建结果目录
    os.makedirs(RESULT_DIR, exist_ok=True)
    
    # 从搜索页面获取每个地点的链接
    links_dir = RESULT_DIR + "/place_links"
    os.makedirs(links_dir, exist_ok=True)
    
    for i in range(MIN_SEARCH_PAGES, MAX_SEARCH_PAGES+1):
        url = f"https://www.lonelyplanet.com/places?type={SEARCH_TYPE}&sort={SORT}&page={i}"
        url_links, _ = scrape_url_links_with_retry(app, url)
        filtered_links = [link for link in url_links 
                        if not link.startswith("https://www.lonelyplanet.com/places?type=")]
        
        if not filtered_links:
            logging.error(f"搜索页面 {url} 未返回有效链接")
            save_failed_urls([url], f"搜索页面 {i}", links_dir)
            continue
            
        save_url_links(
            filtered_links, 
            f"place links crawled from search page {i} (indexed from 1)", 
            f"place_links_{i}", save_dir=links_dir)

    # 获取每个地点的详细信息
    sub_urls = ["attractions", "articles"]
    for i in range(MIN_SEARCH_PAGES, MAX_SEARCH_PAGES+1):
        place_links_file = f"{links_dir}/place_links_{i}.json"
        if not os.path.exists(place_links_file):
            logging.warning(f"地点链接文件 {place_links_file} 不存在，跳过")
            continue
            
        with open(place_links_file, "r", encoding="utf-8") as f:
            place_links_data = json.load(f)
        
        place_links = place_links_data['urls']
        
        url_contents, failed_place_urls = get_batch_url_content_with_retry(app, place_links)
        
        if failed_place_urls:
            save_failed_urls(failed_place_urls, f"地点页面 - 搜索页 {i}", links_dir)
        
        for url_content in url_contents:
            try:
                url_title = get_url_title(url_content)
                url_dir = RESULT_DIR + "/" + url_title
                os.makedirs(url_dir, exist_ok=True)
                
                save_url_content(url_content, 
                                file_name=f"{url_title} main page", 
                                save_dir=url_dir)
                
                for sub_url_type in sub_urls:
                    sub_url = url_content['metadata']['url'].replace("/destinations", "") + "/" + sub_url_type
                    logging.info(f"处理子URL: {sub_url}")
                    
                    sub_url_links = crawl_multi_page_url_links(app, sub_url)
                    
                    if not sub_url_links:
                        logging.error(f"子URL {sub_url} 未返回有效链接")
                        save_failed_urls([sub_url], f"{url_title} {sub_url_type}", url_dir)
                        continue
                    
                    save_url_links(
                        sub_url_links, 
                        f"sub url links crawled from {url_title} {sub_url_type} page", 
                        f"{url_title}_{sub_url_type}_links", save_dir=url_dir)
                    
                    # sub_url_contents, failed_sub_urls = get_batch_url_content_with_retry(app, sub_url_links)
                    
                    # if failed_sub_urls:
                    #     save_failed_urls(failed_sub_urls, f"{url_title} {sub_url_type} page", url_dir)
                    
                    # for sub_url_content in sub_url_contents:
                    #     try:
                    #         sub_url_title = get_url_title(sub_url_content)
                    #         save_url_content(sub_url_content, 
                    #                         file_name=f"{sub_url_title}", 
                    #                         save_dir=url_dir)
                    #     except Exception as e:
                    #         logging.error(f"保存子URL内容出错: {str(e)}")
            except Exception as e:
                logging.error(f"处理URL内容出错: {str(e)}")

def recrawl_failed_urls(app: FirecrawlApp, root_dir: str = RESULT_DIR):
    """重新爬取失败的URL"""
    logging.info("开始重新爬取失败的URL")   
    success = True
    
    for root, dirs, files in os.walk(root_dir):
        if 'failed_urls.json' in files:
            failed_file_path = os.path.join(root, 'failed_urls.json')
            logging.info(f"发现失败URL文件: {failed_file_path}")
            
            with open(failed_file_path, 'r', encoding='utf-8') as f:
                try:
                    failed_data = json.load(f)
                    
                    if 'failed_urls' in failed_data and failed_data['failed_urls']:
                        updated_failed_urls = {}
                        
                        for description, urls in failed_data['failed_urls'].items():
                            if not urls:  # 如果URL列表为空，跳过
                                continue
                                
                            logging.info(f"重新爬取: {description}, URL数量: {len(urls)}")
                            
                            still_failed_urls = []
                            for url in urls:
                                try:
                                    sub_url_links, failed_sub_url_links = crawl_multi_page_url_links(app, url)
                                    if sub_url_links:
                                        
                                        save_url_links(
                                            sub_url_links, 
                                            f"recrawled {description} links from {url}", 
                                            f"{description}_links", 
                                            save_dir=root,
                                            overwrite=True)
                                    else:
                                        still_failed_urls.append(url)
                                        success = False
                                except Exception as e:
                                    logging.error(f"重新爬取链接出错 {url}: {str(e)}")
                                    still_failed_urls.append(url)
                                    success = False
                            
                            if still_failed_urls:
                                updated_failed_urls[description] = still_failed_urls
                                success = False
                        
                        # 更新失败URL文件
                        with open(failed_file_path, 'w', encoding='utf-8') as f_update:
                            json.dump({"failed_urls": updated_failed_urls}, f_update, ensure_ascii=False, indent=4)
                            
                        logging.info(f"更新失败URL文件: {failed_file_path}")
                        
                except json.JSONDecodeError:
                    logging.error(f"解析失败URL文件出错: {failed_file_path}")
                    success = False
                except Exception as e:
                    logging.error(f"处理失败URL文件出错: {str(e)}")
                    success = False
    
    logging.info(f"重新爬取失败的URL {'成功' if success else '部分失败'}")
    return success


if __name__ == "__main__":
    app = FirecrawlApp(API_KEY)
    # main(app)
    recrawl_failed_urls(app, RESULT_DIR + "/place")
 