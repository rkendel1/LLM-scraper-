# backend/utils/database.py

import os
import psycopg2
from psycopg2.extras import Json
from typing import Optional, List, Dict, Any

def get_db():
    """Get a database connection"""
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

def save_to_postgres(
    title: str,
    description: str,
    text: str,
    url: Optional[str],
    embedding: List[float],
    pdf_paths: Optional[List[str]] = None,
    source_type: str = 'web',
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Save document content to PostgreSQL with vector support
    
    Args:
        title (str): Document title
        description (str): Short summary
        text (str): Full extracted text
        url (str): Source URL or None
        embedding (List[float]): Vector embedding
        pdf_paths (List[str], optional): File paths of associated PDFs
        source_type (str): 'web', 'pdf', 'manual', etc.
        metadata (dict, optional): Extra info like domain, author, etc.
    """
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO documents (
              url, title, description, text, embedding, pdf_paths, source_type, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
              title = EXCLUDED.title,
              description = EXCLUDED.description,
              text = EXCLUDED.text,
              embedding = EXCLUDED.embedding,
              pdf_paths = EXCLUDED.pdf_paths,
              metadata = EXCLUDED.metadata,
              source_type = EXCLUDED.source_type
        """, (
            url,
            title,
            description,
            text,
            embedding,
            pdf_paths or [],
            source_type,
            Json(metadata) if metadata else None
        ))
        conn.commit()
        logger.info(f"Saved document: {title} ({url})")

    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
    finally:
        cur.close()
        conn.close()


def hybrid_search(query: str, limit: int = 5):
    """Hybrid search using keyword + semantic similarity"""
    from embedder.embedding_utils import embed_text
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
        logger.error(f"Hybrid search error: {e}")
        return []


def get_document_by_id(doc_id: int):
    """Retrieve full document by ID"""
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, title, text FROM documents WHERE id = %s", (doc_id,))
        result = cur.fetchone()
        cur.close()
        return {
            "id": result[0],
            "title": result[1],
            "text": result[2]
        }
    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        return None
