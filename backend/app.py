# backend/app.py

from flask import Flask, request, jsonify, render_template, render_template_string
import json
import logging
import os
import threading
from typing import Optional, List, Dict, Any

import psycopg2
from psycopg2.extras import Json

# Optional: If you're calling embed_text inside functions, you can move this up for clarity
# from embedder.embedding_utils import embed_text

database_url = os.getenv("DATABASE_URL")
ollama_host = os.getenv("OLLAMA_HOST")
debug_mode = os.getenv("DEBUG", "False").lower() == "true"

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure upload and graph folders exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("graphs", exist_ok=True)

# === Import Modules ===
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from llm.pdf_form_filler import generate_with_mistral
from utils.database import save_to_postgres, get_db
from utils.user_utils import update_user_profile, get_user_profile
from utils.web_search import simple_web_search #extract_content_from_url
from utils.quality_filter import is_quality_result
from utils.delegation_model import should_delegate_query
from utils.ontology_router import route_query_to_agent
from utils.forwarder import forward_to_agent

# Global flag to control crawl
crawl_stop_flag = threading.Event()

# === Helper Functions ===
def has_changed(url, text, domain):
    from processor.change_detector import has_changed as detector
    return detector(url, text, domain)

def download_pdf(pdf_url):
    from processor.pdf_downloader import download_pdf
    return download_pdf(pdf_url)

def analyze_pdf_form(pdf_path):
    from processor.pdf_analyzer import analyze_pdf_form
    return analyze_pdf_form(pdf_path)

def fill_pdf_form(pdf_path, filled_path, field_data):
    from llm.pdf_form_filler import fill_pdf_form
    return fill_pdf_form(pdf_path, filled_path, field_data)

def generate_field_value(name, field_type):
    from llm.pdf_form_filler import generate_field_value
    return generate_field_value(name, field_type)

def build_ontology(docs, domain):
    from graph.ontology_builder import build_ontology
    return build_ontology(docs, domain)

def export_graph_json(docs, domain):
    from graph.ontology_builder import export_graph_json
    return export_graph_json(docs, domain)

# === Routes ===

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start-crawl', methods=['POST'])
def start_crawl():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON payload received"}), 400

    domain = data.get('domain')
    depth = data.get('depth', 2)

    if not domain:
        return jsonify({"error": "Missing 'domain' in request"}), 400

    global crawl_stop_flag
    crawl_stop_flag.clear()

    def crawl_task():
        try:
            docs = run_crawler(domain, depth, stop_event=crawl_stop_flag)
            updated_docs = []
            for doc in docs:
                if crawl_stop_flag.is_set():
                    break
                content = extract_content(doc['html'])
                if not content:
                    continue
                if not has_changed(doc['url'], content['text'], domain):
                    continue
                pdf_paths = []
                for pdf_url in doc.get('pdf_links', []):
                    pdf_path = download_pdf(pdf_url)
                    if pdf_path:
                        analysis = analyze_pdf_form(pdf_path)
                        if analysis['is_form']:
                            field_data = {field['name']: generate_field_value(field['name'], field.get('type', '')) for field in analysis['fields'] if generate_field_value(field['name'], field.get('type', ''))}
                            filled_path = pdf_path.replace('.pdf', '_filled.pdf')
                            fill_pdf_form(pdf_path, filled_path, field_data)
                            pdf_paths.append(filled_path)
                        else:
                            pdf_paths.append(pdf_path)
                embedding = embed_text(content['text'])
                save_to_postgres(title=content['title'], description=content['description'], text=content['text'], url=doc['url'], embedding=embedding, pdf_paths=pdf_paths, source_type='web', metadata={'domain': domain})
                updated_docs.append(doc)
            if not crawl_stop_flag.is_set() and updated_docs:
                build_ontology(updated_docs, domain)
                export_graph_json(updated_docs, domain)
        except Exception as e:
            logger.error(f"Error during crawl: {e}")

    crawl_thread = threading.Thread(target=crawl_task)
    crawl_thread.start()

    return jsonify({"status": "started", "domain": domain})

@app.route('/stop-crawl', methods=['POST'])
def stop_crawl():
    global crawl_stop_flag
    crawl_stop_flag.set()
    return jsonify({"status": "stopping"})

@app.route('/rag/ask', methods=['POST'])
def ask_question():
    from langchain.prompts import ChatPromptTemplate
    from llm.prompt_templates import RAG_PROMPT_TEMPLATE, PROFILE_EXTRACTION_PROMPT
    query = request.json.get('question')
    user_id = request.json.get('user_id')
    if not query:
        return jsonify({"error": "Missing question"}), 400

    try:
        from utils.hybrid_search import hybrid_search
        context_docs = hybrid_search(query, limit=3)
        if not context_docs:
            if should_delegate_query(query):
                target_agent = route_query_to_agent(query)
                if target_agent:
                    return jsonify(forward_to_agent(target_agent, query))
            search_urls = simple_web_search(query, max_results=5)
            new_docs = [url for url in search_urls if is_quality_result(url)]
            context_docs = hybrid_search(query, limit=3)
        profile = get_user_profile(user_id) if user_id else {}
        if user_id:
            profile_prompt = PROFILE_EXTRACTION_PROMPT.format(input=query)
            profile_update_str = generate_with_mistral(profile_prompt)
            try:
                profile_update = json.loads(profile_update_str)
                for key, value in profile_update.items():
                    update_user_profile(user_id, {"key": key, "value": value})
                profile.update(profile_update)
            except:
                pass
        context = "\n\n".join([f"{d['title']}\n{d['text'][:500]}" for d in context_docs])
        full_prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=query)
        answer = generate_with_mistral(full_prompt)
        validation_prompt = f"""
        You are a quality assurance assistant.
        The user asked: "{query}"
        The system answered: "{answer}"
        Based on the context below, is the answer accurate?
        Context: {context}
        Please respond with: - Yes/No for accuracy - A corrected or improved version of the answer - Suggested next steps
        """
        validation_response = generate_with_mistral(validation_prompt).strip().split('\n')
        is_accurate = validation_response[0].lower().startswith("yes")
        improved_answer = validation_response[2] if len(validation_response) > 2 else answer
        next_steps = validation_response[3] if len(validation_response) > 3 else "No specific next steps."
        return jsonify({
            "original_query": query,
            "initial_answer": answer,
            "is_accurate": is_accurate,
            "improved_answer": improved_answer,
            "next_steps": next_steps,
            "sources": [{"title": d["title"], "url": d.get("url")} for d in context_docs],
            "profile_used": profile
        })
    except Exception as e:
        logger.error(f"Error in /rag/ask: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/user/profile', methods=['POST'])
def get_profile():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
    profile = get_user_profile(user_id)
    return jsonify({"profile": profile}) if profile else jsonify({"error": "User not found"}), 404

@app.route('/user/profile/update', methods=['POST'])
def update_profile():
    data = request.json
    user_id = data.get('user_id')
    key = data.get('key')
    value = data.get('value')
    if not all([user_id, key, value]):
        return jsonify({"error": "Missing user_id, key, or value"}), 400
    try:
        update_user_profile(user_id, {"key": key, "value": value})
        return jsonify({"status": "success", "message": f"{key} updated", "key": key, "value": value})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/user/profile/delete', methods=['POST'])
def delete_profile_key():
    data = request.json
    user_id = data.get('user_id')
    key = data.get('key')
    if not user_id or not key:
        return jsonify({"error": "Missing user_id or key"}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET profile = profile #- %s::TEXT[] WHERE id = %s", ('{' + key + '}', user_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "deleted", "key": key})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/auth/register', methods=['POST'])
def register():
    email = request.json.get('email')
    password = request.json.get('password')
    user_id = create_user(email, password)  # Assume this function exists
    return jsonify({"status": "registered", "user_id": user_id}) if user_id else jsonify({"error": "Email already exists"}), 400

@app.route('/auth/verify-email', methods=['POST'])
def verify_email():
    email = request.json.get('email')
    otp = request.json.get('otp')
    return jsonify({"status": "verified", "user_id": 123})  # Simulate success

@app.route('/auth/request-mail-otp', methods=['POST'])
def request_mail_otp():
    user_id = request.json.get('user_id')
    return jsonify({"status": "sent", "message": "Code mailed to user's address"})

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({"error": "No files part"}), 400
    files = request.files.getlist('files')
    uploaded_paths = []
    for file in files:
        if file.filename == '':
            continue
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)
        uploaded_paths.append(file_path)
    return jsonify({"status": "uploaded", "files": uploaded_paths})

@app.route('/graph/<domain>')
def view_graph(domain):
    graph_file = f"graphs/{domain}.json"
    if os.path.exists(graph_file):
        with open(graph_file) as f:
            graph_data = f.read()
    else:
        graph_data = json.dumps({"nodes": [], "links": []})  # Default empty graph
    return render_template_string(open("graphs/viewer/index.html").read(), GRAPH_DATA=graph_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
