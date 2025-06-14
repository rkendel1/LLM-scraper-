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

    print(f"Starting crawl on {domain} with depth {depth}")
    docs = run_crawler(domain, depth)

    processed_docs = []
    for doc in docs:
        content = extract_content(doc['html'])

        embedding = embed_text(content['text'])

        processed_doc = {
            **content,
            'url': doc['url'],
            'embedding': embedding
        }

        save_to_postgres(processed_doc)
        processed_docs.append(processed_doc)

    return jsonify({"status": "completed", "docs": len(processed_docs)})


def save_to_postgres(doc):
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
    """, (
        doc['url'], doc['title'], doc['description'], doc['text'], doc['embedding']
    ))
    conn.commit()
    cur.close()
    conn.close()

@app.route('/search', methods=['POST'])
def semantic_search():
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "Missing query"}), 400

    embedding = embed_text(query)

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        SELECT url, title, description, 1 - (embedding <=> %s::vector) AS cosine_similarity
        FROM documents
        ORDER BY embedding <-> %s::vector
        LIMIT 5
    """, (embedding, embedding))
    results = cur.fetchall()
    cur.close()

    return jsonify([{
        "url": r[0],
        "title": r[1],
        "description": r[2],
        "similarity": 1 - r[3]
    } for r in results])
