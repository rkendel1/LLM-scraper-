# utils/user_utils.py

import os
import logging
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extras import Json
from passlib.hash import bcrypt

from .database import get_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




def create_user(email: str, password: str, profile: Optional[Dict[str, Any]] = None):
    """
    Create a new user with email and hashed password.
    Optionally include initial profile data.
    """
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        pwd_hash = bcrypt.hash(password)

        cur.execute("""
            INSERT INTO users (email, password_hash, profile)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            RETURNING id
        """, (email, pwd_hash, Json(profile) if profile else '{}'))

        result = cur.fetchone()
        conn.commit()
        return result[0] if result else None

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error creating user: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id, email, password_hash, profile FROM users WHERE email = %s", (email,))
        result = cur.fetchone()
        if not result:
            return None

        return {
            "id": result[0],
            "email": result[1],
            "password_hash": result[2],
            "profile": result[3] or {}
        }

    except Exception as e:
        logger.error(f"❌ Error fetching user: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_user_profile(user_id: int) -> Dict[str, Any]:
    """Retrieve user profile by ID"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT profile FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        return result[0] if result else {}

    except Exception as e:
        logger.error(f"❌ Error fetching profile: {e}")
        return {}


def update_user_profile(user_id: int, updates: Dict[str, Any]):
    """
    Update user profile field(s)
    
    Example:
      update_user_profile(1, {"key": "address", "value": "7 Spinnaker Ln"})
    """
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        key = updates.get("key")
        value = updates.get("value")

        if not key:
            logger.warning("❌ Missing 'key' in update request")
            return {"error": "Missing key"}

        cur.execute("""
            UPDATE users
            SET profile = jsonb_set(profile, %s::TEXT[], %s::JSONB, true)
            WHERE id = %s
            RETURNING profile
        """, ('{' + key + '}', Json(value), user_id))

        conn.commit()
        result = cur.fetchone()
        return {"status": "success", "profile": result[0]}

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error updating profile: {e}")
        return {"error": str(e)}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def delete_profile_key(user_id: int, key: str):
    """Remove a key from user profile"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE users
            SET profile = profile #- %s::TEXT[]
            WHERE id = %s
            RETURNING profile
        """, ('{' + key + '}', user_id))

        conn.commit()
        result = cur.fetchone()
        return {"status": "deleted", "profile": result[0]}

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def verify_password(email: str, password: str, stored_hash: Optional[str] = None) -> bool:
    """Verify user password"""
    if not stored_hash:
        user = get_user_by_email(email)
        if not user:
            return False
        stored_hash = user["password_hash"]

    return bcrypt.verify(password, stored_hash)


def update_user_password(user_id: int, new_password: str):
    """Update user password"""
    conn = None
    cur = None
    try:
        conn = get_db()
        cur = conn.cursor()

        pwd_hash = bcrypt.hash(new_password)
        cur.execute("""
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
        """, (pwd_hash, user_id))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
