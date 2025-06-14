from flask import Flask, request, jsonify
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
import os
import psycopg2

app = Flask(__name__)


from graph.ontology_builder import build_ontology, export_graph_json
from processor.pdf_downloader import download_pdf

from processor.pdf_downloader import download_pdf
from processor.pdf_analyzer import analyze_pdf_form
from processor.llm_form_filler import generate_field_value
from processor.pdf_form_filler import fill_pdf_form

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

        if not has_changed(doc['url'], content['text'], domain):
            continue

        # Handle PDF links
        pdf_paths = []
        for pdf_url in doc.get('pdf_links', []):
            pdf_path = download_pdf(pdf_url)
            if not pdf_path:
                continue

            analysis = analyze_pdf_form(pdf_path)
            if analysis['is_form']:
                field_data = {}
                for field in analysis['fields']:
                    name = field['name']
                    field_type = field['type']
                    value = generate_field_value(name, field_type)
                    field_data[name] = value

                filled_path = pdf_path.replace('.pdf', '_filled.pdf')
                fill_pdf_form(pdf_path, filled_path, field_data)
                pdf_paths.append(filled_path)
            else:
                pdf_paths.append(pdf_path)

        embedding = embed_text(content['text'])
        save_to_postgres(content, doc['url'], embedding, pdf_paths)
        updated_docs.append(doc)

    return jsonify({"status": "completed", "docs_updated": len(updated_docs)})
    
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

@app.route('/pdf/<filename>')
def serve_pdf(filename):
    return send_from_directory('pdfs/', filename)
