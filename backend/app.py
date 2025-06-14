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
