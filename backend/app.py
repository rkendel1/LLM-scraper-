# backend/app.py

from flask import Flask, request, jsonify, send_from_directory
import os

# Import modules
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from processor.pdf_downloader import download_pdf
from processor.pdf_analyzer import analyze_pdf_form
from llm.pdf_form_filler import generate_field_value, fill_pdf_form
from graph.ontology_builder import build_ontology, export_graph_json
from utils.database import save_to_postgres
from processor.change_detector import has_changed

app = Flask(__name__)

# Ensure directories exist
os.makedirs("pdfs", exist_ok=True)


@app.route('/start-crawl', methods=['POST'])
def start_crawl():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON payload received"}), 400

    domain = data.get('domain')
    depth = data.get('depth', 2)

    if not domain:

@app.route('/query', methods=['POST'])
def hybrid_search():
    query = request.json.get('query')
    embedding = embed_text(query)
    
    results = db.execute("""
        SELECT id, title, text,
               ts_rank(to_tsvector(text), plainto_tsquery(%s)) AS keyword_score,
               1 - (embedding <=> %s::vector) AS semantic_score,
               (ts_rank(to_tsvector(text), plainto_tsquery(%s)) * 0.4 +
                (1 - (embedding <=> %s::vector)) * 0.6) AS hybrid_score
        FROM documents
        ORDER BY hybrid_score DESC
        LIMIT 5
    """, (query, embedding, query, embedding))
