from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from services.rag_service import get_relevant_documents
from models.database import get_db

router = APIRouter(prefix="/rag")

@router.post("/ask")
async def ask_question(
    question: str,
    db: Session = Depends(get_db)
):
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    relevant_docs = get_relevant_documents(db, question)
    if not relevant_docs:
        return {"answer": "No relevant documents found.", "sources": []}

    # For now, just return top doc content
    answer = relevant_docs[0]['text'][:300] + "..."  # Simplified demo
    sources = [{"url": d["url"], "title": d["title"], "similarity": d["similarity"]} for d in relevant_docs]

    return {"answer": answer, "sources": sources}
