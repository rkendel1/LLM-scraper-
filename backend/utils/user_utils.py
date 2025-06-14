# utils/user_utils.py

from passlib.hash import bcrypt
import psycopg2

def update_user_profile(user_id, updates):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE users
            SET profile = jsonb_set(profile, %s::TEXT[], %s::JSONB, true)
            WHERE id = %s
        """, (
            '{' + updates["key"] + '}',
            f'"{updates["value"]}"',
            user_id
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error updating profile: {e}")
    finally:
        cur.close()
        conn.close()
