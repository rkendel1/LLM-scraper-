from sentence_transformers import SentenceTransformer
import numpy as np
from sqlalchemy.orm import Session

model = SentenceTransformer('all-MiniLM-L6-v2')

def get_relevant_documents(db: Session, query: str, limit: int = 5):
    embedding = model.encode(query).tolist()

    # Query your scraper's documents table
    result = db.execute("""
        SELECT url, title, description, text, 1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        ORDER BY embedding <-> %s::vector
        LIMIT %s
    """, (embedding, embedding, limit))

    return [
        {
            "url": row[0],
            "title": row[1],
            "description": row[2],
            "text": row[3],
            "similarity": row[4]
        }
        for row in result
    ]
