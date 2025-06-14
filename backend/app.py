# backend/app.py

from flask import Flask, request, jsonify
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Initialize Flask app
app = Flask(__name__)

# Ensure upload folder exists
os.makedirs("uploads", exist_ok=True)

# === Import Modules ===
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from llm.pdf_form_filler import generate_with_mistral
from utils.database import save_to_postgres, get_db
from utils.web_search import duckduckgo_search, extract_content_from_url
from utils.quality_filter import is_quality_result
from utils.delegation_model import should_delegate_query
from utils.ontology_router import route_query_to_agent
from utils.forwarder import forward_to_agent


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
        app.logger.error(f"Error during crawl: {e}")
        return jsonify({"error": str(e)}), 500


# === Route: Ask a Question (RAG Pipeline) ===
@app.route('/rag/ask', methods=['POST'])
def ask_question():
    query = request.json.get('question')
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

            # Step 3: No agent found — fall back to DuckDuckGo search
            search_urls = duckduckgo_search(query, max_results=5)
            new_docs = []

            for url in search_urls:
                if is_quality_result(url):
                    new_docs.append(url)

            # Re-run hybrid search now that we've added new documents
            context_docs = hybrid_search(query, limit=3)

        # Generate final answer using Mistral
        context = "\n\n".join([f"{d['title']}\n{d['text'][:500]}" for d in context_docs])
        prompt = f"""
        Answer the following question based on the provided context:

        Question: {query}

        Context:
        {context}
        """
        answer = generate_with_mistral(prompt)

        # Validate and suggest next steps
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
            "sources": [{"title": d["title"], "url": d.get("url")} for d in context_docs]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
