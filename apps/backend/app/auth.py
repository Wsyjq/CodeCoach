import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from app.config import settings
from app.db.database import get_connection, initialize_database

PASSWORD_ITERATIONS = 210_000
TOKEN_TTL_DAYS = 14


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return secrets.compare_digest(actual, expected)


def create_user(username: str, display_name: str, password: str) -> dict[str, Any]:
    initialize_database()
    now = _utc_now()
    user_id = f"user_{secrets.token_hex(8)}"
    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (id, username, display_name, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, display_name or username, hash_password(password), now),
            )
            connection.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Username already exists") from exc
        raise
    user = get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=500, detail="User creation failed")
    return user


def get_user_by_username(username: str) -> dict[str, Any] | None:
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, display_name, password_hash, created_at, last_login_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, display_name, created_at, last_login_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def create_session(user_id: str) -> str:
    initialize_database()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    expires_at = (now_dt + timedelta(days=TOKEN_TTL_DAYS)).isoformat()
    token = secrets.token_urlsafe(32)
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO user_sessions (token, user_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
            (token, user_id, now, expires_at, now),
        )
        connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id))
        connection.commit()
    return token


def delete_session(token: str) -> None:
    initialize_database()
    with get_connection() as connection:
        connection.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        connection.commit()


def current_user(authorization: str = Header(default="")) -> dict[str, Any]:
    token = _bearer_token(authorization)
    if not token:
        if settings.auth_required:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return _demo_user()

    user = user_from_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def current_user_id(user: dict[str, Any] = Depends(current_user)) -> str:
    return str(user["id"])


def user_from_token(token: str) -> dict[str, Any] | None:
    initialize_database()
    now = _utc_now()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT users.id, users.username, users.display_name, users.created_at, users.last_login_at, user_sessions.expires_at
            FROM user_sessions
            JOIN users ON users.id = user_sessions.user_id
            WHERE user_sessions.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= now:
            connection.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
            connection.commit()
            return None
        connection.execute("UPDATE user_sessions SET last_seen_at = ? WHERE token = ?", (now, token))
        connection.commit()
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


def public_user(user: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(user["id"]),
        "username": str(user["username"]),
        "display_name": str(user["display_name"]),
    }


def _bearer_token(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return ""
    return token.strip()


def _demo_user() -> dict[str, str]:
    return {
        "id": settings.demo_user_id,
        "username": settings.demo_user_id,
        "display_name": "Demo 用户",
        "created_at": "",
        "last_login_at": "",
    }


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
