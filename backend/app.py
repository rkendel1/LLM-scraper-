# backend/app.py

from flask import Flask, request, jsonify, send_from_directory
import os
import psycopg2

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

# Initialize Flask app
app = Flask(__name__)

# Ensure directories exist
os.makedirs("pdfs", exist_ok=True)


# === Helper: Get DB Connection ===
def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


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
                metadata={
                    'domain': domain,
                    'source_type': 'web'
                }
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


# === Route: Serve PDFs ===
@app.route('/pdf/<filename>')
def serve_pdf_file(filename):
    return send_from_directory('pdfs', filename)


# === Helper: Hybrid Search Function ===
def hybrid_search(query, limit=5):
    embedding = embed_text(query)
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, title, text,
                   ts_rank(to_tsvector(text), plainto_tsquery(%s)) AS keyword_score,
                   1 - (embedding <=> %s::vector) AS semantic_score,
                   (ts_rank(to_tsvector(text), plainto_tsquery(%s)) * 0.4 +
                    (1 - (embedding <=> %s::vector)) * 0.6) AS hybrid_score
            FROM documents
            ORDER BY hybrid_score DESC
            LIMIT %s
        """, (query, embedding, query, embedding, limit))

        results = cur.fetchall()
        cur.close()
        conn.close()

        return [{
            "id": r[0],
            "title": r[1],
            "text": r[2],
            "keyword_score": r[3],
            "semantic_score": r[4],
            "hybrid_score": r[5]
        } for r in results]

    except Exception as e:
        print("Hybrid search error:", e)
        return []


# === Route: RAG Ask with Validation & Next Steps ===
@app.route('/rag/ask', methods=['POST'])
def ask_question():
    from llm.pdf_form_filler import generate_with_mistral

    query = request.json.get('question')
    if not query:
        return jsonify({"error": "Missing question"}), 400

    # Step 1: Get relevant documents using hybrid search
    context_docs = hybrid_search(query, limit=3)
    if not context_docs:
        return jsonify({"answer": "No relevant documents found."})

    # Step 2: Generate initial answer
    context = "\n\n".join([f"{d['title']}\n{d['text'][:500]}" for d in context_docs])
    prompt = f"""
    Answer the following question based on the provided context:

    Question: {query}

    Context:
    {context}
    """
    answer = generate_with_mistral(prompt)

    # Step 3: Validate and suggest next steps
    validation_prompt = f"""
    You are a quality assurance assistant.

    The user asked: "{query}"
    The system answered: "{answer}"

    Based on the context below, is the answer accurate? If not, what should be done?

    Context:
    {context}

    Please respond with:
    - Yes/No for accuracy
    - A corrected or improved version of the answer
    - Suggested next steps (e.g., refine query, check more docs, etc.)
    """
    validation_response = generate_with_mistral(validation_prompt)

    # Parse response manually
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
        "sources": [{"title": d["title"], "url": d["url"]} for d in context_docs]
    })


# === Run App ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
