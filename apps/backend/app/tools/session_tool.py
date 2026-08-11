import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.db.database import get_connection, initialize_database
from app.schemas.chat import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


def load_session_context(user_id: str, session_id: str, limit: int = 5) -> list[dict]:
    if not session_id:
        return []
    try:
        initialize_database()
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT role, intent, message, answer, problem_text, code, context_json, turn_id, created_at
                FROM chat_logs
                WHERE user_id = ? AND session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, session_id, limit * 2),
            ).fetchall()
        return [_chat_log_row_to_dict(row) for row in reversed(rows)]
    except Exception:
        logger.exception("load_session_context failed for user=%s session=%s", user_id, session_id)
        return []


def write_chat_log(user_id: str, session_id: str, turn_id: str, request: ChatRequest, response: ChatResponse) -> None:
    try:
        initialize_database()
        now = datetime.now(timezone.utc).isoformat()
        context_json = json.dumps(
            {
                "conversation_title": response.conversation_title,
                "knowledge_type": response.knowledge_type,
                "knowledge_tags": response.knowledge_tags,
                "review_card_id": response.review_card.id,
                "review_card_title": response.review_card.title,
            },
            ensure_ascii=False,
        )
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_logs (
                    id, user_id, session_id, turn_id, role, intent, message, answer,
                    problem_text, code, context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"chat_user_{uuid4().hex}",
                    user_id,
                    session_id,
                    turn_id,
                    "user",
                    response.intent,
                    request.message,
                    "",
                    request.problem_text,
                    request.code,
                    context_json,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO chat_logs (
                    id, user_id, session_id, turn_id, role, intent, message, answer,
                    problem_text, code, context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"chat_assistant_{uuid4().hex}",
                    user_id,
                    session_id,
                    turn_id,
                    "assistant",
                    response.intent,
                    "",
                    response.answer,
                    request.problem_text,
                    request.code,
                    context_json,
                    now,
                ),
            )
            connection.commit()
    except Exception:
        logger.exception("write_chat_log failed for user=%s session=%s turn=%s", user_id, session_id, turn_id)


def _chat_log_row_to_dict(row) -> dict:
    try:
        context = json.loads(row["context_json"] or "{}")
    except json.JSONDecodeError:
        context = {}
    return {
        "role": row["role"],
        "intent": row["intent"],
        "message": row["message"],
        "answer": row["answer"],
        "problem_text": row["problem_text"],
        "code": row["code"],
        "context": context,
        "turn_id": row["turn_id"],
        "created_at": row["created_at"],
    }
