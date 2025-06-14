# utils/quality_filter.py

from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from utils.database import save_to_postgres

def is_quality_result(url, min_length=200):
    try:
        html = requests.get(url, timeout=10).text
        cleaned = extract_content(html)
        
        if not cleaned or len(cleaned['text'].split()) < min_length:
            return False

        # Embed and save
        embedding = embed_text(cleaned['text'])
        save_to_postgres(
            title=cleaned['title'],
            description=cleaned['description'],
            text=cleaned['text'],
            url=url,
            embedding=embedding,
            source_type='web_search',
            metadata={"source": "free_search"}
        )
        return True
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return False
