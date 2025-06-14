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

app = Flask(__name__)

# Ensure directories exist
os.makedirs("pdfs", exist_ok=True)

# Database connection (move to utils/database.py ideally)
def get_db():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn


# === Routes ===

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


@app.route('/pdf/<filename>')
def serve_pdf_file(filename):
    return send_from_directory('pdfs', filename)


@app.route('/query', methods=['POST'])
def hybrid_search():
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "Missing query"}), 400

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
            LIMIT 5
        """, (query, embedding, query, embedding))

        results = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "id": r[0],
            "title": r[1],
            "text_snippet": r[2][:300],
            "keyword_score": r[3],
            "semantic_score": r[4],
            "hybrid_score": r[5]
        } for r in results])

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/rag/ask', methods=['POST'])
def ask_question():
    query = request.json.get('question')
    if not query:
        return jsonify({"error": "Missing question"}), 400

    # Get relevant documents using vector search
    try:
        conn = get_db()
        cur = conn.cursor()
        embedding = embed_text(query)

        cur.execute("""
            SELECT id, title, text, 1 - (embedding <=> %s::vector) AS similarity
            FROM documents
            ORDER BY embedding <-> %s::vector
            LIMIT 3
        """, (embedding, embedding))

        context_docs = [{
            "id": r[0],
            "title": r[1],
            "text": r[2],
            "similarity": r[3]
        } for r in cur.fetchall()]
        cur.close()
        conn.close()

        # Generate prompt
        context = "\n\n".join([f"{d['title']}\n{d['text'][:300]}" for d in context_docs])
        prompt = f"""
        Answer the following question based on the provided context:

        Question: {query}

        Context:
        {context}
        """

        # Call Mistral via Ollama or local model
        from llm.pdf_form_filler import generate_with_mistral
        answer = generate_with_mistral(prompt)

        return jsonify({
            "answer": answer,
            "sources": [{"title": d["title"], "url": d["source_id"]} for d in context_docs]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
