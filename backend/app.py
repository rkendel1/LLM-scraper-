# backend/app.py

from flask import Flask, request, jsonify
import os
import json
import logging

# Initialize Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure upload folder exists
os.makedirs("uploads", exist_ok=True)

# === Import Modules ===
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from llm.pdf_form_filler import generate_with_mistral
from utils.database import save_to_postgres, get_db, get_user_profile, update_user_profile
from utils.web_search import duckduckgo_search, extract_content_from_url
from utils.quality_filter import is_quality_result
from utils.delegation_model import should_delegate_query
from utils.ontology_router import route_query_to_agent
from utils.forwarder import forward_to_agent


# === Helper: Has Changed? ===
def has_changed(url, text, domain):
    from processor.change_detector import has_changed as detector
    return detector(url, text, domain)


# === Helper: Download PDFs ===
def download_pdf(pdf_url):
    from processor.pdf_downloader import download_pdf
    return download_pdf(pdf_url)


# === Helper: Analyze PDF Forms ===
def analyze_pdf_form(pdf_path):
    from processor.pdf_analyzer import analyze_pdf_form
    return analyze_pdf_form(pdf_path)


# === Helper: Fill PDF Form Fields ===
def fill_pdf_form(pdf_path, filled_path, field_data):
    from llm.pdf_form_filler import fill_pdf_form
    return fill_pdf_form(pdf_path, filled_path, field_data)


# === Helper: Generate Field Value ===
def generate_field_value(name, field_type):
    from llm.pdf_form_filler import generate_field_value
    return generate_field_value(name, field_type)


# === Helper: Build Ontology Graph ===
def build_ontology(docs, domain):
    from graph.ontology_builder import build_ontology
    return build_ontology(docs, domain)


def export_graph_json(docs, domain):
    from graph.ontology_builder import export_graph_json
    return export_graph_json(docs, domain)


# === Route: Start Web Crawl ===
@app.route('/start-crawl', methods=['POST'])
def start_crawl():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON payload received"}), 400

    domain = data.get('domain')
    depth = data.get('depth', 2)

    if not domain:
        return jsonify({"error": "Missing 'domain' in request"}), 400

    try:
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
                        field_type = field.get('type', '')
                        value = generate_field_value(name, field_type)
                        if value:
                            field_data[name] = value

                    filled_path = pdf_path.replace('.pdf', '_filled.pdf')
                    fill_pdf_form(pdf_path, filled_path, field_data)
                    pdf_paths.append(filled_path)
                else:
                    pdf_paths.append(pdf_path)

            # Embed text
            embedding = embed_text(content['text'])

            # Save to PostgreSQL
            save_to_postgres(
                title=content['title'],
                description=content['description'],
                text=content['text'],
                url=doc['url'],
                embedding=embedding,
                pdf_paths=pdf_paths,
                source_type='web',
                metadata={'domain': domain}
            )
            updated_docs.append(doc)

        # Build ontology graph
        if updated_docs:
            build_ontology(updated_docs, domain)
            export_graph_json(updated_docs, domain)

        return jsonify({
            "status": "completed",
            "docs_updated": len(updated_docs),
            "domain": domain
        })

    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        return jsonify({"error": str(e)}), 500


# === Route: Ask a Question (RAG + User Profile Aware) ===
@app.route('/rag/ask', methods=['POST'])
def ask_question():
    from langchain.prompts import ChatPromptTemplate
    from llm.prompt_templates import RAG_PROMPT_TEMPLATE, PROFILE_EXTRACTION_PROMPT

    query = request.json.get('question')
    user_id = request.json.get('user_id')  # Optional
    if not query:
        return jsonify({"error": "Missing question"}), 400

    try:
        # Step 1: Try answering locally
        from utils.hybrid_search import hybrid_search
        context_docs = hybrid_search(query, limit=3)

        if not context_docs:
            # Step 2: Should we delegate?
            from utils.delegation_model import should_delegate_query
            if should_delegate_query(query):
                target_agent = route_query_to_agent(query)
                if target_agent:
                    forwarded_answer = forward_to_agent(target_agent, query)
                    return jsonify(forwarded_answer)

            # Step 3: No agent — fall back to web search
            search_urls = duckduckgo_search(query, max_results=5)
            new_docs = []

            for url in search_urls:
                if is_quality_result(url):
                    new_docs.append(url)

            # Re-run hybrid search now that we've added new documents
            context_docs = hybrid_search(query, limit=3)

        # Step 4: Get user profile if available
        profile = {}
        if user_id:
            profile = get_user_profile(user_id)

            # Step 5: Detect and save new profile info from input
            profile_prompt = PROFILE_EXTRACTION_PROMPT.format(input=query)
            profile_update_str = generate_with_mistral(profile_prompt)
            try:
                profile_update = json.loads(profile_update_str)
                for key, value in profile_update.items():
                    update_user_profile(user_id, {"key": key, "value": value})
                profile.update(profile_update)
            except:
                pass  # Not valid JSON

        # Step 6: Generate final answer using Mistral
        context = "\n\n".join([f"{d['title']}\n{d['text'][:500]}" for d in context_docs])
        full_prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=query)

        answer = generate_with_mistral(full_prompt)

        # Step 7: Validate and improve
        validation_prompt = f"""
        You are a quality assurance assistant.
        
        The user asked: "{query}"
        The system answered: "{answer}"

        Based on the context below, is the answer accurate?

        Context:
        {context}

        Please respond with:
        - Yes/No for accuracy
        - A corrected or improved version of the answer
        - Suggested next steps (e.g., refine query, check more docs, etc.)
        """
        validation_response = generate_with_mistral(validation_prompt)
        lines = validation_response.strip().split('\n')

        is_accurate = lines[0].lower().startswith("yes")
        improved_answer = lines[2] if len(lines) > 2 else answer
        next_steps = lines[3] if len(lines) > 3 else "No specific next steps."

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


# === Route: User Profile Routes (optional) ===
@app.route('/user/profile', methods=['POST'])
def get_profile():
    user_id = request.json.get('user_id')
    profile = get_user_profile(user_id)
    if profile:
        return jsonify({"profile": profile})
    return jsonify({"error": "User not found"}), 404


@app.route('/user/profile/update', methods=['POST'])
def update_profile():
    data = request.json
    user_id = data.get('user_id')
    key = data.get('key')
    value = data.get('value')

    if not all([user_id, key, value]):
        return jsonify({"error": "Missing user_id, key, or value"}), 400

    update_user_profile(user_id, {"key": key, "value": value})
    return jsonify({"status": "updated", "key": key})

@app.route('/user/profile', methods=['POST'])
def get_profile():
    """Get user profile by ID"""
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    profile = get_user_profile(user_id)
    if profile:
        return jsonify({"profile": profile})
    return jsonify({"error": "User not found"}), 404


@app.route('/user/profile/update', methods=['POST'])
def update_profile():
    """Update specific field in user profile"""
    data = request.json
    user_id = data.get('user_id')
    key = data.get('key')
    value = data.get('value')

    if not all([user_id, key, value]):
        return jsonify({"error": "Missing user_id, key, or value"}), 400

    try:
        update_user_profile(user_id, {"key": key, "value": value})
        return jsonify({
            "status": "success",
            "message": f"{key} updated",
            "key": key,
            "value": value
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/user/profile/delete', methods=['POST'])
def delete_profile_key():
    """Remove a key from user profile"""
    data = request.json
    user_id = data.get('user_id')
    key = data.get('key')

    if not user_id or not key:
        return jsonify({"error": "Missing user_id or key"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE users
            SET profile = profile #- %s::TEXT[]
            WHERE id = %s
        """, ('{' + key + '}', user_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "status": "deleted",
            "key": key
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
