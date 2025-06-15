from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import logging
import threading
import json
import psycopg2
from psycopg2.extras import Json

# === Import Modules ===
from crawler.scrapy_spider import run_crawler
from processor.cleaner import extract_content
from embedder.embedding_utils import embed_text
from llm.pdf_form_filler import generate_with_mistral
from utils.database import save_to_postgres, get_db
from utils.user_utils import update_user_profile, get_user_profile
from utils.web_search import simple_web_search
from utils.quality_filter import is_quality_result
from utils.delegation_model import should_delegate_query
from utils.ontology_router import route_query_to_agent
from utils.forwarder import forward_to_agent

# Initialize FastAPI app
app = FastAPI(
    title="LLM Scraper API",
    description="Scrape URLs, process PDFs, build ontologies, and use LLMs for RAG.",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up template engine
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
database_url = os.getenv("DATABASE_URL")
ollama_host = os.getenv("OLLAMA_HOST")
debug_mode = os.getenv("DEBUG", "False").lower() == "true"

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("graphs", exist_ok=True)

# Global flag to control crawl
crawl_stop_flag = threading.Event()

# Helper functions (unchanged)
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

# Pydantic Models
class CrawlRequest(BaseModel):
    domain: str
    depth: int = 2

class AskQuestionRequest(BaseModel):
    question: str
    user_id: Optional[str] = None

class UserProfileRequest(BaseModel):
    user_id: str

class ProfileUpdateRequest(BaseModel):
    user_id: str
    key: str
    value: str

class RegisterRequest(BaseModel):
    email: str
    password: str

class VerifyEmailRequest(BaseModel):
    email: str
    otp: str

class UploadFilesRequest(BaseModel):
    files: List[str]

# === Routes ===

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start-crawl")
async def start_crawl(request: CrawlRequest):
    global crawl_stop_flag
    crawl_stop_flag.clear()
    
    def crawl_task():
        try:
            docs = run_crawler(request.domain, request.depth, stop_event=crawl_stop_flag)
            updated_docs = []
            for doc in docs:
                if crawl_stop_flag.is_set():
                    break
                content = extract_content(doc['html'])
                if not content:
                    continue
                if not has_changed(doc['url'], content['text'], request.domain):
                    continue
                pdf_paths = []
                for pdf_url in doc.get('pdf_links', []):
                    pdf_path = download_pdf(pdf_url)
                    if pdf_path:
                        analysis = analyze_pdf_form(pdf_path)
                        if analysis['is_form']:
                            field_data = {
                                field['name']: generate_field_value(field['name'], field.get('type', ''))
                                for field in analysis['fields']
                                if generate_field_value(field['name'], field.get('type', ''))
                            }
                            filled_path = pdf_path.replace('.pdf', '_filled.pdf')
                            fill_pdf_form(pdf_path, filled_path, field_data)
                            pdf_paths.append(filled_path)
                        else:
                            pdf_paths.append(pdf_path)
                embedding = embed_text(content['text'])
                save_to_postgres(
                    title=content['title'],
                    description=content['description'],
                    text=content['text'],
                    url=doc['url'],
                    embedding=embedding,
                    pdf_paths=pdf_paths,
                    source_type='web',
                    metadata={'domain': request.domain}
                )
                updated_docs.append(doc)
            if not crawl_stop_flag.is_set() and updated_docs:
                build_ontology(updated_docs, request.domain)
                export_graph_json(updated_docs, request.domain)
        except Exception as e:
            logger.error(f"Error during crawl: {e}")

    crawl_thread = threading.Thread(target=crawl_task)
    crawl_thread.start()
    return {"status": "started", "domain": request.domain}

@app.post("/stop-crawl")
async def stop_crawl():
    global crawl_stop_flag
    crawl_stop_flag.set()
    return {"status": "stopping"}

@app.post("/rag/ask")
async def ask_question(data: AskQuestionRequest):
    from langchain.prompts import ChatPromptTemplate
    from llm.prompt_templates import RAG_PROMPT_TEMPLATE, QA_WITH_PROFILE_PROMPT
    query = data.question
    user_id = data.user_id

    if not query:
        raise HTTPException(status_code=400, detail="Missing question")

    try:
        from utils.hybrid_search import hybrid_search
        context_docs = hybrid_search(query, limit=3)

        if not context_docs:
            if should_delegate_query(query):
                target_agent = route_query_to_agent(query)
                if target_agent:
                    return forward_to_agent(target_agent, query)

            search_urls = simple_web_search(query, max_results=5)
            new_docs = [url for url in search_urls if is_quality_result(url)]
            context_docs = hybrid_search(query, limit=3)

        profile = get_user_profile(user_id) if user_id else {}

        if user_id:
            profile_prompt = QA_WITH_PROFILE_PROMPT.format(input=query)
            profile_update_str = generate_with_mistral(profile_prompt)
            try:
                profile_update = json.loads(profile_update_str)
                for key, value in profile_update.items():
                    update_user_profile(user_id, {"key": key, "value": value})
                profile.update(profile_update)
            except Exception:
                pass

        context = "\n".join([f"{d['title']}\n{d['text'][:500]}" for d in context_docs])
        full_prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=query)
        answer = generate_with_mistral(full_prompt)

        validation_prompt = f"""
        You are a quality assurance assistant.
        The user asked: "{query}"
        The system answered: "{answer}"
        Based on the context below, is the answer accurate?
        Context: {context}
        Please respond with: 
        - Yes/No for accuracy
        - A corrected or improved version of the answer
        - Suggested next steps
        """
        validation_response = generate_with_mistral(validation_prompt).strip().split('\n')
        is_accurate = validation_response[0].lower().startswith("yes")
        improved_answer = validation_response[2] if len(validation_response) > 2 else answer
        next_steps = validation_response[3] if len(validation_response) > 3 else "No specific next steps."

        return {
            "original_query": query,
            "initial_answer": answer,
            "is_accurate": is_accurate,
            "improved_answer": improved_answer,
            "next_steps": next_steps,
            "sources": [{"title": d["title"], "url": d.get("url")} for d in context_docs],
            "profile_used": profile
        }

    except Exception as e:
        logger.error(f"Error in /rag/ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/profile")
async def get_profile(data: UserProfileRequest):
    user_id = data.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")
    profile = get_user_profile(user_id)
    if profile:
        return {"profile": profile}
    else:
        raise HTTPException(status_code=404, detail="User not found")

@app.post("/user/profile/update")
async def update_profile(data: ProfileUpdateRequest):
    user_id = data.user_id
    key = data.key
    value = data.value
    if not all([user_id, key, value]):
        raise HTTPException(status_code=400, detail="Missing user_id, key, or value")
    try:
        update_user_profile(user_id, {"key": key, "value": value})
        return {"status": "success", "message": f"{key} updated", "key": key, "value": value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/profile/delete")
async def delete_profile_key(data: ProfileUpdateRequest):
    user_id = data.user_id
    key = data.key
    if not user_id or not key:
        raise HTTPException(status_code=400, detail="Missing user_id or key")
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET profile = profile #- %s::TEXT[] WHERE id = %s", ('{' + key + '}', user_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "deleted", "key": key}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/register")
async def register(data: RegisterRequest):
    email = data.email
    password = data.password
    # Assume create_user function exists
    user_id = create_user(email, password)
    if user_id:
        return {"status": "registered", "user_id": user_id}
    else:
        raise HTTPException(status_code=400, detail="Email already exists")

@app.post("/auth/verify-email")
async def verify_email():
    return {"status": "verified", "user_id": 123}  # Simulate success

@app.post("/auth/request-mail-otp")
async def request_mail_otp(data: UserProfileRequest):
    return {"status": "sent", "message": "Code mailed to user's address"}

@app.post("/upload")
async def upload_files(files: List[str] = Body(...)):
    uploaded_paths = []
    for filename in files:
        if filename == '':
            continue
        file_path = os.path.join('uploads', filename)
        # Simulating file save (replace with actual upload handling)
        uploaded_paths.append(file_path)
    return {"status": "uploaded", "files": uploaded_paths}

@app.get("/graph/{domain}")
async def view_graph(domain: str):
    graph_file = f"graphs/{domain}.json"
    if os.path.exists(graph_file):
        with open(graph_file, "r") as f:
            graph_data = f.read()
    else:
        graph_data = json.dumps({"nodes": [], "links": []})  # Default empty graph
    return {"GRAPH_DATA": graph_data}
