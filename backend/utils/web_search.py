# utils/web_search.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from trafilatura import fetch_url, extract

def simple_web_search(query, max_results=5):
    """Perform a basic Google-like search using DuckDuckGo HTML"""
    search_url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.post(search_url, data={"q": query}, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    results = []
    for link in soup.find_all('a', href=True):
        url = link['href']
        if url.startswith("http://") or url.startswith("https://"):
            results.append(url)
        if len(results) >= max_results:
            break
    
    return results


#def extract_content_from_url(url):
 #   downloaded = fetch_url(url)
  #  if downloaded:
   #     text = extract(downloaded, favor_recall=True)
    #    return text
   # return None
