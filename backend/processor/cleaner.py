import trafilatura
from langdetect import detect
from langchain.text_splitter import RecursiveCharacterTextSplitter

def extract_content(html):
    result = trafilatura.bare_extraction(html, favor_recall=True)

    if not result or not result['text']:
        return None

    # Language filtering
    try:
        lang = detect(result['text'])
        if lang != 'en':
            return None
    except:
        pass

    # Text quality check
    if len(result['text'].split()) < 200:
        return None

    # Clean and chunk
    title = result.get('title', '')
    description = result.get('excerpt', '')
    full_text = result['text']

    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
    chunks = splitter.split_text(full_text)

    return {
        'title': title,
        'description': description,
        'text': full_text,
        'chunks': chunks,
        'url': result.get('url'),
        'pub_date': result.get('date')
    }
