from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from qqa.rag_service import get_relevant_documents
from models.database import get_db

router = APIRouter(prefix="/rag")

@router.post("/ask")
def ask_question(question: str, db: Session = Depends(get_db)):
    if not question:
        return {"error": "Question is required"}

    results = get_relevant_documents(db, question)
    answer = results[0]['text'][:300] + "..." if results else "No relevant info found."
    sources = [{"url": r["url"], "title": r["title"], "similarity": r["similarity"]} for r in results]

    return {"answer": answer, "sources": sources}
