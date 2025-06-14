from flask import Flask, request, jsonify
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
import os
import psycopg2

app = Flask(__name__)

@app.route('/start-crawl', methods=['POST'])
def start_crawl():
    data = request.json
    domain = data.get('domain')
    depth = data.get('depth', 2)

    docs = run_crawler(domain, depth)
    processed_docs = []

    for doc in docs:
        content = extract_content(doc['html'])
        embedding = embed_text(content['text'])

        save_to_postgres(
            content['title'],
            content['description'],
            content['text'],
            doc['url'],
            embedding
        )
        processed_docs.append(doc['url'])

    return jsonify({"status": "completed", "docs": len(processed_docs)})


def save_to_postgres(title, description, text, url, embedding):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (url, title, description, text, embedding)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (url) DO UPDATE SET
          title = EXCLUDED.title,
          description = EXCLUDED.description,
          text = EXCLUDED.text,
          embedding = EXCLUDED.embedding
    """, (url, title, description, text, embedding))
    conn.commit()
    cur.close()
    conn.close()
from processor.change_detector import has_changed

@app.route('/start-crawl', methods=['POST'])
def start_crawl():
    data = request.json
    domain = data.get('domain')
    depth = data.get('depth', 2)

    docs = run_crawler(domain, depth)
    updated_docs = []

    for doc in docs:
        content = extract_content(doc['html'])
        if not content:
            continue

        # Skip unchanged pages
        if not has_changed(doc['url'], content['text'], domain):
            print(f"Skipped unchanged: {doc['url']}")
            continue

        embedding = embed_text(content['text'])
        save_to_postgres(content, doc['url'], embedding)
        updated_docs.append(doc['url'])

    return jsonify({"status": "completed", "docs_updated": len(updated_docs)})
