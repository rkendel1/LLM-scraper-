# backend/utils/database.py

import os
import logging
import psycopg2
from psycopg2.extras import Json
from typing import Optional, List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        logger.info("✅ PostgreSQL connection established.")
        return conn
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        raise


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
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

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
        logger.info(f"✅ Saved document: {title} ({url})")

    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def hybrid_search(query: str, limit: int = 5):
    """
    Hybrid search using keyword + semantic similarity
    
    Returns list of matching documents ranked by hybrid score.
    """
    from embedder.embedding_utils import embed_text
    embedding = embed_text(query)

    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

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
        logger.error(f"❌ Hybrid search error: {e}")
        return []


def get_document_by_id(doc_id: int):
    """Retrieve full document by ID"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id, title, text FROM documents WHERE id = %s", (doc_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        return {
            "id": result[0],
            "title": result[1],
            "text": result[2]
        } if result else None

    except Exception as e:
        logger.error(f"❌ Error fetching document: {e}")
        return None


def vector_search(embedding: List[float], limit: int = 5):
    """Search documents using vector similarity"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, title, text, 1 - (embedding <=> %s::vector) AS similarity
            FROM documents
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        """, (embedding, embedding, limit))

        results = cur.fetchall()
        cur.close()
        conn.close()

        return [{
            "id": r[0],
            "title": r[1],
            "text": r[2],
            "similarity": r[3]
        } for r in results]

    except Exception as e:
        logger.error(f"❌ Vector search error: {e}")
        return []


# ---------------- User Profile Utilities ----------------
def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user profile by user ID"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT profile FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"❌ Error fetching user profile: {e}")
        return None
