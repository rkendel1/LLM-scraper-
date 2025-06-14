# backend/app.py

from flask import Flask, request, jsonify, send_from_directory
import os
import psycopg2
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)

# Config
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'md'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# === Import Modules ===
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from processor.pdf_analyzer import analyze_pdf_form, fill_pdf_form
from llm.pdf_form_filler import generate_with_mistral
from utils.database import save_to_postgres, get_db
from processor.change_detector import has_changed


# === Helper Functions ===

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path):
    ext = file_path.split('.')[-1].lower()

    if ext == 'pdf':
        from PyPDF2 import PdfReader
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            return ' '.join([page.extract_text() for page in reader.pages if page.extract_text()])

    elif ext in ['txt', 'md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    elif ext == 'docx':
        import docx2txt
        return docx2txt.process(file_path)

    else:
        import textract
        return textract.process(file_path).decode('utf-8')


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


@app.route('/upload/pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            # Extract text
            text = extract_text_from_file(file_path)
            cleaned_text = extract_content(text)['text']  # Use cleaner.py
            embedding = embed_text(cleaned_text)

            # Save to DB
            save_to_postgres(
                title=filename,
                description=cleaned_text[:200],
                text=cleaned_text,
                url=None,
                embedding=embedding,
                pdf_paths=[file_path],
                source_type='pdf',
                metadata={"filename": filename}
            )

            return jsonify({
                "status": "success",
                "message": "PDF processed and saved",
                "title": filename,
                "text_snippet": cleaned_text[:300]
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "File type not supported"}), 400


@app.route('/upload/text', methods=['POST'])
def upload_text():
    data = request.get_json()
    raw_text = data.get('text')
    title = data.get('title', 'Untitled')
    source_id = data.get('source_id')

    if not raw_text:
        return jsonify({"error": "Missing text"}), 400

    try:
        # Clean and chunk
        cleaned_text = extract_content("<p>" + raw_text + "</p>")['text']
        embedding = embed_text(cleaned_text)

        # Save to DB
        save_to_postgres(
            title=title,
            description=cleaned_text[:200],
            text=cleaned_text,
            url=None,
            embedding=embedding,
            pdf_paths=[],
            source_type='manual',
            metadata={"source_id": source_id}
        )

        return jsonify({
            "status": "success",
            "title": title,
            "text_snippet": cleaned_text[:300]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
                    (1 - (embedding <=> %s::vector)) * 0.6 AS hybrid_score
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
            "hybrid_score": r[5]
        } for r in results])

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# backend/app.py

@app.route('/rag/ask', methods=['POST'])
def ask_question():
    from utils.ontology_router import route_query_to_agent

    query = request.json.get('question')
    if not query:
        return jsonify({"error": "Missing question"}), 400

    try:
        # Try answering locally first
        context_docs = hybrid_search(query, limit=3)
        if not context_docs:
            # No local results — decide whether to forward
            should_delegate = should_delegate_query(query)
            if should_delegate:
                target_agent = route_query_to_agent(query)
                if target_agent:
                    forwarded_answer = forward_to_agent(target_agent, query)
                    return jsonify(forwarded_answer)

        # Generate local answer
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
        - Suggested next steps
        """
        validation_response = generate_with_mistral(validation_prompt)
        ...

        return jsonify({...})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
