SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_login_at TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_cards (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL,
        problem_text TEXT NOT NULL DEFAULT '',
        user_code TEXT NOT NULL DEFAULT '',
        error_type TEXT NOT NULL,
        knowledge_type TEXT NOT NULL DEFAULT 'UNKNOWN',
        knowledge_tags TEXT NOT NULL,
        mistake_summary TEXT NOT NULL,
        review_tip TEXT NOT NULL,
        remember_points TEXT NOT NULL DEFAULT '[]',
        understand_points TEXT NOT NULL DEFAULT '[]',
        common_mistakes TEXT NOT NULL DEFAULT '[]',
        memory_key TEXT NOT NULL DEFAULT '',
        question_key TEXT NOT NULL DEFAULT '',
        issue_type TEXT NOT NULL DEFAULT '',
        occurrence_count INTEGER NOT NULL DEFAULT 1,
        mastery_status TEXT NOT NULL DEFAULT 'reviewing',
        review_count INTEGER NOT NULL DEFAULT 0,
        last_reviewed_at TEXT NOT NULL DEFAULT '',
        first_seen_at TEXT NOT NULL DEFAULT '',
        last_seen_at TEXT NOT NULL,
        next_review_at TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT '',
        last_recalled_at TEXT NOT NULL DEFAULT '',
        recall_count INTEGER NOT NULL DEFAULT 0,
        mastery REAL NOT NULL DEFAULT 0.3,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS concept_mastery (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        concept TEXT NOT NULL,
        wrong_count INTEGER NOT NULL DEFAULT 0,
        review_count INTEGER NOT NULL DEFAULT 0,
        mastery REAL NOT NULL DEFAULT 0.3,
        mastery_score REAL NOT NULL DEFAULT 0.3,
        mastery_status TEXT NOT NULL DEFAULT 'reviewing',
        last_seen_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_logs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL DEFAULT '',
        turn_id TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT 'assistant',
        intent TEXT NOT NULL DEFAULT '',
        message TEXT NOT NULL,
        answer TEXT NOT NULL DEFAULT '',
        problem_text TEXT NOT NULL DEFAULT '',
        code TEXT NOT NULL DEFAULT '',
        context_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_traces (
        id TEXT PRIMARY KEY,
        chat_log_id TEXT NOT NULL,
        user_id TEXT NOT NULL DEFAULT '',
        session_id TEXT NOT NULL DEFAULT '',
        turn_id TEXT NOT NULL DEFAULT '',
        tool_name TEXT NOT NULL DEFAULT '',
        input_json TEXT NOT NULL DEFAULT '{}',
        output_json TEXT NOT NULL DEFAULT '{}',
        node TEXT NOT NULL,
        status TEXT NOT NULL,
        detail TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_events (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        memory_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        mastery_before REAL NOT NULL DEFAULT 0,
        mastery_after REAL NOT NULL DEFAULT 0,
        next_review_at TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
]


COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "users": {
        "last_login_at": "TEXT NOT NULL DEFAULT ''",
    },
    "user_sessions": {
        "last_seen_at": "TEXT NOT NULL DEFAULT ''",
    },
    "review_cards": {
        "session_id": "TEXT NOT NULL DEFAULT ''",
        "problem_text": "TEXT NOT NULL DEFAULT ''",
        "user_code": "TEXT NOT NULL DEFAULT ''",
        "knowledge_type": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
        "remember_points": "TEXT NOT NULL DEFAULT '[]'",
        "understand_points": "TEXT NOT NULL DEFAULT '[]'",
        "common_mistakes": "TEXT NOT NULL DEFAULT '[]'",
        "memory_key": "TEXT NOT NULL DEFAULT ''",
        "question_key": "TEXT NOT NULL DEFAULT ''",
        "issue_type": "TEXT NOT NULL DEFAULT ''",
        "occurrence_count": "INTEGER NOT NULL DEFAULT 1",
        "mastery_status": "TEXT NOT NULL DEFAULT 'reviewing'",
        "review_count": "INTEGER NOT NULL DEFAULT 0",
        "last_reviewed_at": "TEXT NOT NULL DEFAULT ''",
        "first_seen_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
        "last_recalled_at": "TEXT NOT NULL DEFAULT ''",
        "recall_count": "INTEGER NOT NULL DEFAULT 0",
    },
    "concept_mastery": {
        "wrong_count": "INTEGER NOT NULL DEFAULT 0",
        "review_count": "INTEGER NOT NULL DEFAULT 0",
        "mastery_score": "REAL NOT NULL DEFAULT 0.3",
        "mastery_status": "TEXT NOT NULL DEFAULT 'reviewing'",
        "last_seen_at": "TEXT NOT NULL DEFAULT ''",
    },
    "chat_logs": {
        "session_id": "TEXT NOT NULL DEFAULT ''",
        "turn_id": "TEXT NOT NULL DEFAULT ''",
        "role": "TEXT NOT NULL DEFAULT 'assistant'",
        "problem_text": "TEXT NOT NULL DEFAULT ''",
        "code": "TEXT NOT NULL DEFAULT ''",
        "context_json": "TEXT NOT NULL DEFAULT '{}'",
    },
    "tool_traces": {
        "user_id": "TEXT NOT NULL DEFAULT ''",
        "session_id": "TEXT NOT NULL DEFAULT ''",
        "turn_id": "TEXT NOT NULL DEFAULT ''",
        "tool_name": "TEXT NOT NULL DEFAULT ''",
        "input_json": "TEXT NOT NULL DEFAULT '{}'",
        "output_json": "TEXT NOT NULL DEFAULT '{}'",
    },
}
