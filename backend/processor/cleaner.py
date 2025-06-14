from bs4 import BeautifulSoup
import re

def extract_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style']):
        tag.decompose()

    title = soup.title.string if soup.title else ''
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc["content"] if meta_desc else ''

    text = re.sub(r'\s+', ' ', soup.get_text()).strip()
    return {
        'title': title,
        'description': description,
        'text': text
    }
