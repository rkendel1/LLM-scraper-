from flask import Flask, request, jsonify
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
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

        processed_doc = {
            **content,
            'url': doc['url'],
        }

        save_to_postgres(processed_doc)
        processed_docs.append(processed_doc)

    return jsonify({"status": "completed", "docs": len(processed_docs)})

def save_to_postgres(doc):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (url, title, description, text)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
    """, (
        doc['url'], doc['title'], doc['description'], doc['text']
    ))
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
