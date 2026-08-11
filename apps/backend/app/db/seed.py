import json

from app.db.database import get_connection, initialize_database


DEMO_REVIEW_CARDS = [
    {
        "id": "review_001",
        "user_id": "demo_user",
        "title": "scanf 输入错误",
        "error_type": "C语法错误",
        "knowledge_type": "MEMORIZE",
        "knowledge_tags": ["C语言", "scanf", "输入"],
        "mistake_summary": "用户在 scanf 中忘记给普通变量加 &。",
        "review_tip": "读取普通变量时通常要传变量地址。",
        "remember_points": ["scanf 读取普通变量时通常要加 &"],
        "understand_points": ["scanf 需要变量地址，才能把输入值写回变量"],
        "common_mistakes": ["把 scanf(\"%d\", &n) 写成 scanf(\"%d\", n)"],
        "last_seen_at": "2026-07-08",
        "next_review_at": "2026-07-09",
        "mastery": 0.42,
        "mastery_status": "reviewing",
        "created_at": "2026-07-08",
    },
    {
        "id": "review_002",
        "user_id": "demo_user",
        "title": "数组越界与循环边界",
        "error_type": "循环边界错误",
        "knowledge_type": "UNDERSTAND",
        "knowledge_tags": ["C语言", "数组", "循环边界"],
        "mistake_summary": "循环条件写成 i <= n，导致访问 a[n]。",
        "review_tip": "长度为 n 的数组最后一个下标是 n - 1。",
        "remember_points": ["长度为 n 的数组最后一个合法下标是 n - 1"],
        "understand_points": ["循环条件 <= n 会访问到 a[n]，超出数组边界"],
        "common_mistakes": ["把 i < n 写成 i <= n", "数组开小但按更大范围访问"],
        "last_seen_at": "2026-07-07",
        "next_review_at": "2026-07-09",
        "mastery": 0.36,
        "mastery_status": "reviewing",
        "created_at": "2026-07-07",
    },
    {
        "id": "review_003",
        "user_id": "demo_user",
        "title": "二分查找边界不收缩",
        "error_type": "算法边界错误",
        "knowledge_type": "UNDERSTAND",
        "knowledge_tags": ["算法", "二分查找", "循环边界"],
        "mistake_summary": "更新 left = mid 后区间可能不变，导致死循环。",
        "review_tip": "二分更新时要确认新区间严格变小，例如 left = mid + 1。",
        "remember_points": ["二分每次更新边界后，区间必须严格变小"],
        "understand_points": ["当 mid 等于 left 时，left = mid 不会推进搜索区间"],
        "common_mistakes": ["left = mid 导致死循环", "边界更新没有跳过 mid"],
        "last_seen_at": "2026-07-06",
        "next_review_at": "2026-07-10",
        "mastery": 0.55,
        "mastery_status": "reviewing",
        "created_at": "2026-07-06",
    },
]


def seed_demo_data() -> None:
    initialize_database()
    with get_connection() as connection:
        for item in DEMO_REVIEW_CARDS:
            existing = connection.execute(
                "SELECT 1 FROM review_cards WHERE id = ?",
                (item["id"],),
            ).fetchone()
            if existing:
                continue
            connection.execute(
                """
                INSERT INTO review_cards (
                    id, user_id, title, error_type, knowledge_type, knowledge_tags,
                    mistake_summary, review_tip, remember_points, understand_points,
                    common_mistakes, mastery_status, last_seen_at, next_review_at,
                    mastery, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["user_id"],
                    item["title"],
                    item["error_type"],
                    item["knowledge_type"],
                    json.dumps(item["knowledge_tags"], ensure_ascii=False),
                    item["mistake_summary"],
                    item["review_tip"],
                    json.dumps(item["remember_points"], ensure_ascii=False),
                    json.dumps(item["understand_points"], ensure_ascii=False),
                    json.dumps(item["common_mistakes"], ensure_ascii=False),
                    item["mastery_status"],
                    item["last_seen_at"],
                    item["next_review_at"],
                    item["mastery"],
                    item["created_at"],
                ),
            )
        connection.commit()
