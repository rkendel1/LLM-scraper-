# backend/utils/database.py

import os
import psycopg2
from psycopg2.extras import Json


def save_to_postgres(title, description, text, url, embedding, pdf_paths=None):
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO documents (url, title, description, text, embedding, pdf_paths)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
              title = EXCLUDED.title,
              description = EXCLUDED.description,
              text = EXCLUDED.text,
              embedding = EXCLUDED.embedding,
              pdf_paths = EXCLUDED.pdf_paths
        """, (
            url,
            title,
            description,
            text,
            embedding,
            pdf_paths or []
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
    finally:
        cur.close()
        conn.close()
