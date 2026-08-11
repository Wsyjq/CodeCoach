import json
from datetime import datetime, timezone
from uuid import uuid4

from app.db.database import get_connection, initialize_database


def write_tool_trace(
    user_id: str,
    session_id: str,
    turn_id: str,
    tool_name: str,
    input_data: dict | list | str,
    output_data: dict | list | str,
    status: str = "done",
    detail: str = "",
) -> None:
    try:
        initialize_database()
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO tool_traces (
                    id, chat_log_id, user_id, session_id, turn_id, tool_name,
                    input_json, output_json, node, status, detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"trace_{uuid4().hex}",
                    turn_id,
                    user_id,
                    session_id,
                    turn_id,
                    tool_name,
                    _json_dump(input_data),
                    _json_dump(output_data),
                    tool_name,
                    status,
                    detail,
                    now,
                ),
            )
            connection.commit()
    except Exception:
        return


def list_tool_traces(user_id: str = "demo_user", session_id: str = "", turn_id: str = "") -> list[dict]:
    try:
        initialize_database()
        clauses = ["user_id = ?"]
        params: list[str] = [user_id]
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if turn_id:
            clauses.append("turn_id = ?")
            params.append(turn_id)
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, user_id, session_id, turn_id, tool_name, input_json,
                       output_json, status, detail, created_at
                FROM tool_traces
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at ASC
                """,
                tuple(params),
            ).fetchall()
        return [_trace_row_to_dict(row) for row in rows]
    except Exception:
        return []


def _trace_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_id": row["session_id"],
        "turn_id": row["turn_id"],
        "tool_name": row["tool_name"],
        "input": _json_load(row["input_json"]),
        "output": _json_load(row["output_json"]),
        "status": row["status"],
        "detail": row["detail"],
        "created_at": row["created_at"],
    }


def _json_dump(value: dict | list | str) -> str:
    if isinstance(value, str):
        return json.dumps({"value": value}, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_load(raw_value: str) -> dict | list:
    try:
        value = json.loads(raw_value or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, (dict, list)) else {"value": value}
