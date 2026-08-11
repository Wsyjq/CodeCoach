import json
import logging
import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.db.database import get_connection, initialize_database
from app.db.seed import seed_demo_data
from app.schemas.chat import ReviewCard, SimilarMemory
from app.vectorstore.chroma_client import COLLECTION_MEMORIES, search_similar, upsert_documents

logger = logging.getLogger(__name__)


DEMO_MEMORIES = [
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
    },
]


def list_demo_memories(user_id: str) -> list[dict]:
    sqlite_items = _list_sqlite_memories(user_id)
    if sqlite_items:
        return sqlite_items
    return [item for item in DEMO_MEMORIES if item["user_id"] == user_id]


def get_memory_by_id(user_id: str, memory_id: str) -> dict | None:
    for item in list_demo_memories(user_id):
        if item["id"] == memory_id:
            return item
    return None


def mark_memory_reviewed(user_id: str, memory_id: str, outcome: str) -> dict | None:
    memory = get_memory_by_id(user_id, memory_id)
    if memory is None:
        return None

    today = date.today()
    current_mastery = float(memory.get("mastery", 0.3) or 0.3)
    if outcome == "again":
        mastery = max(current_mastery - 0.08, 0.1)
        mastery_status = "reviewing"
        next_review_at = (today + timedelta(days=1)).isoformat()
    elif outcome == "mastered":
        mastery = max(current_mastery, 0.9)
        mastery_status = "mastered"
        next_review_at = (today + timedelta(days=14)).isoformat()
    else:
        mastery = min(current_mastery + 0.15, 0.9)
        mastery_status = "reviewing"
        next_review_at = (today + timedelta(days=3)).isoformat()

    try:
        initialize_database()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE review_cards
                SET mastery = ?, mastery_status = ?, next_review_at = ?, last_seen_at = ?,
                    last_reviewed_at = ?, review_count = review_count + 1
                WHERE id = ? AND user_id = ?
                """,
                (mastery, mastery_status, next_review_at, today.isoformat(), today.isoformat(), memory_id, user_id),
            )
            connection.execute(
                """
                INSERT INTO review_events (
                    id, user_id, memory_id, outcome, mastery_before,
                    mastery_after, next_review_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"event_{uuid4().hex}",
                    user_id,
                    memory_id,
                    outcome,
                    current_mastery,
                    mastery,
                    next_review_at,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            for tag in memory.get("knowledge_tags", []):
                concept_id = f"{user_id}_{tag}"
                connection.execute(
                    """
                    INSERT INTO concept_mastery (
                        id, user_id, concept, wrong_count, review_count, mastery,
                        mastery_score, mastery_status, last_seen_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        review_count = review_count + 1,
                        mastery = excluded.mastery,
                        mastery_score = excluded.mastery_score,
                        mastery_status = excluded.mastery_status,
                        last_seen_at = excluded.last_seen_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        concept_id,
                        user_id,
                        tag,
                        0,
                        1,
                        mastery,
                        mastery,
                        mastery_status,
                        today.isoformat(),
                        today.isoformat(),
                    ),
                )
            connection.commit()
    except Exception:
        logger.exception("mark_memory_reviewed failed for memory=%s outcome=%s", memory_id, outcome)
        return memory
    return get_memory_by_id(user_id, memory_id)


def save_review_card(
    user_id: str,
    review_card: ReviewCard,
    knowledge_tags: list[str] | None = None,
    mistake_summary: str = "",
    review_tip: str = "",
    mastery: float = 0.3,
    session_id: str = "",
    problem_text: str = "",
    user_code: str = "",
    remember_points: list[str] | None = None,
    understand_points: list[str] | None = None,
    common_mistakes: list[str] | None = None,
    knowledge_type: str = "",
    mastery_status: str = "reviewing",
    issue_type: str = "",
) -> ReviewCard:
    try:
        initialize_database()
        today = date.today()
        tags = knowledge_tags or review_card.knowledge_tags
        final_mistake_summary = mistake_summary or review_card.mistake_summary
        final_review_tip = review_tip or review_card.review_tip
        final_remember_points = remember_points or review_card.remember_points
        final_understand_points = understand_points or review_card.understand_points
        final_common_mistakes = common_mistakes or review_card.common_mistakes
        final_knowledge_type = knowledge_type or review_card.knowledge_type
        final_issue_type = issue_type or _issue_type_from_review_card(review_card)
        memory_key = build_memory_key(user_id, final_issue_type, tags)
        question_key = build_question_key(user_id, problem_text, user_code)
        saved = ReviewCard(
            id=f"{review_card.id}_{uuid4().hex[:8]}",
            title=review_card.title,
            error_type=review_card.error_type,
            knowledge_type=final_knowledge_type,  # type: ignore[arg-type]
            knowledge_tags=tags,
            mistake_summary=final_mistake_summary,
            review_tip=final_review_tip,
            remember_points=final_remember_points,
            understand_points=final_understand_points,
            common_mistakes=final_common_mistakes,
            next_review_at=(today + timedelta(days=1)).isoformat(),
        )
        with get_connection() as connection:
            existing = (
                _find_memory_by_question_key(connection, user_id, question_key)
                or _find_memory_by_exact_question(connection, user_id, problem_text, user_code)
                or _find_memory_by_key(connection, user_id, memory_key)
            )
            if existing:
                merged_mastery = min(float(existing["mastery"] or mastery), mastery)
                connection.execute(
                    """
                    UPDATE review_cards
                    SET session_id = ?, title = ?, problem_text = CASE WHEN problem_text = '' THEN ? ELSE problem_text END,
                        user_code = CASE WHEN user_code = '' THEN ? ELSE user_code END,
                        error_type = ?, knowledge_type = ?, knowledge_tags = ?,
                        mistake_summary = ?, review_tip = ?, remember_points = ?,
                        understand_points = ?, common_mistakes = ?, memory_key = ?,
                        question_key = CASE WHEN question_key = '' THEN ? ELSE question_key END,
                        issue_type = ?,
                        occurrence_count = occurrence_count + 1, mastery_status = ?,
                        last_seen_at = ?, next_review_at = ?, mastery = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        session_id,
                        saved.title,
                        problem_text,
                        user_code,
                        saved.error_type,
                        saved.knowledge_type,
                        json.dumps(saved.knowledge_tags, ensure_ascii=False),
                        saved.mistake_summary,
                        saved.review_tip,
                        json.dumps(saved.remember_points, ensure_ascii=False),
                        json.dumps(saved.understand_points, ensure_ascii=False),
                        json.dumps(saved.common_mistakes, ensure_ascii=False),
                        memory_key,
                        question_key,
                        final_issue_type,
                        mastery_status,
                        today.isoformat(),
                        saved.next_review_at,
                        merged_mastery,
                        today.isoformat(),
                        existing["id"],
                        user_id,
                    ),
                )
                _write_concept_wrong_counts(connection, user_id, saved.knowledge_tags, merged_mastery, mastery_status, today.isoformat())
                connection.commit()
                updated = get_memory_by_id(user_id, existing["id"])
                if updated:
                    saved = _review_card_from_memory(updated)
                try:
                    _index_learning_memory_record(updated) if updated else None
                except Exception:
                    logger.warning("ChromaDB index failed for updated memory %s", existing["id"], exc_info=True)
                return saved

            connection.execute(
                """
                INSERT INTO review_cards (
                    id, user_id, session_id, title, problem_text, user_code, error_type,
                    knowledge_type, knowledge_tags, mistake_summary, review_tip,
                    remember_points, understand_points, common_mistakes, memory_key,
                    question_key, issue_type, occurrence_count, mastery_status, first_seen_at,
                    last_seen_at, next_review_at, mastery, updated_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    saved.id,
                    user_id,
                    session_id,
                    saved.title,
                    problem_text,
                    user_code,
                    saved.error_type,
                    saved.knowledge_type,
                    json.dumps(saved.knowledge_tags, ensure_ascii=False),
                    saved.mistake_summary,
                    saved.review_tip,
                    json.dumps(saved.remember_points, ensure_ascii=False),
                    json.dumps(saved.understand_points, ensure_ascii=False),
                    json.dumps(saved.common_mistakes, ensure_ascii=False),
                    memory_key,
                    question_key,
                    final_issue_type,
                    1,
                    mastery_status,
                    today.isoformat(),
                    today.isoformat(),
                    saved.next_review_at,
                    mastery,
                    today.isoformat(),
                    today.isoformat(),
                ),
            )
            _write_concept_wrong_counts(connection, user_id, saved.knowledge_tags, mastery, mastery_status, today.isoformat())
            connection.commit()
        try:
            _index_learning_memory(user_id, saved, memory_key=memory_key, issue_type=final_issue_type, mastery=mastery, mastery_status=mastery_status)
        except Exception:
            logger.warning("ChromaDB index failed for new memory %s", saved.id, exc_info=True)
        return saved
    except Exception:
        logger.exception("save_review_card failed for user=%s issue_type=%s", user_id, issue_type or review_card.id)
        return review_card


def search_learning_memory(user_id: str, query: str, top_k: int = 1) -> SimilarMemory:
    vector_match = _search_vector_memory(user_id, query, top_k=top_k)
    if vector_match.matched:
        return vector_match

    memories = list_demo_memories(user_id)
    if not memories:
        return SimilarMemory(matched=False)
    candidates = sorted(
        (
            (_score_memory_match(query, item), item)
            for item in memories
        ),
        key=lambda candidate: candidate[0],
        reverse=True,
    )[:top_k]
    if candidates and candidates[0][0] >= 0.3:
        score, item = candidates[0]
        _record_memory_recall(user_id, item["id"])
        return SimilarMemory(
            matched=True,
            id=item["id"],
            title=item["title"],
            mistake_summary=item["mistake_summary"],
            review_tip=item["review_tip"],
            score=round(score, 2),
            first_seen_at=item.get("first_seen_at", ""),
            last_seen_at=item.get("last_seen_at", ""),
            occurrence_count=int(item.get("occurrence_count", 0) or 0),
        )
    return SimilarMemory(matched=False)


def build_memory_key(user_id: str, issue_type: str, tags: list[str]) -> str:
    normalized_issue = issue_type.strip() or "unknown_issue"
    normalized_tags = [tag.strip() for tag in tags if tag.strip()]
    return f"{user_id}:{normalized_issue}:{'|'.join(normalized_tags)}"


def build_question_key(user_id: str, problem_text: str, user_code: str) -> str:
    normalized_problem = _normalize_question_text(problem_text)
    normalized_code = _normalize_question_code(user_code)
    if not normalized_problem and not normalized_code:
        return ""
    digest = hashlib.sha256(f"{normalized_problem}\n---code---\n{normalized_code}".encode("utf-8")).hexdigest()[:20]
    return f"{user_id}:question:{digest}"


def find_exact_question_memory(user_id: str, problem_text: str, user_code: str) -> dict | None:
    question_key = build_question_key(user_id, problem_text, user_code)
    if not question_key:
        return None
    try:
        initialize_database()
        seed_demo_data()
        with get_connection() as connection:
            existing = _find_memory_by_question_key(connection, user_id, question_key) or _find_memory_by_exact_question(
                connection,
                user_id,
                problem_text,
                user_code,
            )
        if not existing:
            return None
        memory = get_memory_by_id(user_id, existing["id"])
        if memory:
            _record_memory_recall(user_id, memory["id"])
        return memory
    except Exception:
        logger.warning("find_exact_question_memory failed for user=%s", user_id, exc_info=True)
        return None


def similar_memory_from_record(memory: dict, score: float = 1.0, exact_match: bool = False) -> SimilarMemory:
    return SimilarMemory(
        matched=True,
        id=str(memory.get("id") or ""),
        title=str(memory.get("title") or ""),
        mistake_summary=str(memory.get("mistake_summary") or ""),
        review_tip=str(memory.get("review_tip") or ""),
        score=round(score, 2),
        first_seen_at=str(memory.get("first_seen_at") or memory.get("created_at") or ""),
        last_seen_at=str(memory.get("last_seen_at") or ""),
        occurrence_count=int(memory.get("occurrence_count", 0) or 0),
        exact_match=exact_match,
    )


def reindex_learning_memories(user_id: str | None = None) -> dict:
    try:
        initialize_database()
        clauses = []
        params: list[str] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, user_id, title, error_type, knowledge_type, knowledge_tags,
                       mistake_summary, review_tip, remember_points, understand_points,
                       common_mistakes, session_id, problem_text, user_code,
                       memory_key, question_key, issue_type, occurrence_count, first_seen_at,
                       last_seen_at, next_review_at, updated_at, last_recalled_at,
                       recall_count, mastery, mastery_status, review_count, last_reviewed_at,
                       created_at
                FROM review_cards
                {where_sql}
                ORDER BY created_at ASC
                """,
                tuple(params),
            ).fetchall()
        indexed_count = 0
        failed_count = 0
        for row in rows:
            if _index_learning_memory_record(_review_row_to_dict(row)):
                indexed_count += 1
            else:
                failed_count += 1
        return {"indexed_count": indexed_count, "failed_count": failed_count}
    except Exception:
        return {"indexed_count": 0, "failed_count": 0}


def _index_learning_memory(
    user_id: str,
    review_card: ReviewCard,
    memory_key: str = "",
    issue_type: str = "",
    mastery: float = 0.3,
    mastery_status: str = "reviewing",
) -> bool:
    document = _build_learning_memory_text(review_card)
    metadata = {
        "review_id": review_card.id,
        "user_id": user_id,
        "title": review_card.title,
        "error_type": review_card.error_type,
        "knowledge_type": review_card.knowledge_type,
        "tags": ",".join(review_card.knowledge_tags),
        "memory_key": memory_key,
        "issue_type": issue_type,
        "mastery": mastery,
        "mastery_status": mastery_status,
        "next_review_at": review_card.next_review_at,
        "mistake_summary": review_card.mistake_summary,
        "review_tip": review_card.review_tip,
    }
    return upsert_documents(COLLECTION_MEMORIES, [review_card.id], [document], [metadata])


def _index_learning_memory_record(memory: dict) -> bool:
    return _index_learning_memory(
        user_id=str(memory.get("user_id") or ""),
        review_card=_review_card_from_memory(memory),
        memory_key=str(memory.get("memory_key") or ""),
        issue_type=str(memory.get("issue_type") or ""),
        mastery=float(memory.get("mastery", 0.3) or 0.3),
        mastery_status=str(memory.get("mastery_status") or "reviewing"),
    )


def _search_vector_memory(user_id: str, query: str, top_k: int = 1) -> SimilarMemory:
    results = search_similar(COLLECTION_MEMORIES, query, top_k=top_k, where={"user_id": user_id})
    if not results:
        return SimilarMemory(matched=False)
    best = results[0]
    score = float(best.get("score", 0) or 0)
    if score < 0.3:
        return SimilarMemory(matched=False)
    metadata = best.get("metadata", {}) or {}
    review_id = str(metadata.get("review_id") or best.get("id") or "")
    if review_id:
        _record_memory_recall(user_id, review_id)
    return SimilarMemory(
        matched=True,
        title=str(metadata.get("title") or "相似错题"),
        mistake_summary=str(metadata.get("mistake_summary") or ""),
        review_tip=str(metadata.get("review_tip") or ""),
        score=round(score, 2),
    )


def _build_learning_memory_text(review_card: ReviewCard) -> str:
    return "\n".join(
        [
            f"标题：{review_card.title}",
            f"错误类型：{review_card.error_type}",
            f"知识类型：{review_card.knowledge_type}",
            f"知识点：{','.join(review_card.knowledge_tags)}",
            f"错误总结：{review_card.mistake_summary}",
            f"复习建议：{review_card.review_tip}",
        ]
    )


def _list_sqlite_memories(user_id: str) -> list[dict]:
    try:
        seed_demo_data()
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, title, error_type, knowledge_type, knowledge_tags,
                       mistake_summary, review_tip, remember_points, understand_points,
                       common_mistakes, session_id, problem_text, user_code,
                       memory_key, question_key, issue_type, occurrence_count, first_seen_at,
                       last_seen_at, next_review_at, updated_at, last_recalled_at,
                       recall_count, mastery, mastery_status, review_count, last_reviewed_at,
                       created_at
                FROM review_cards
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return _collapse_exact_question_duplicates([_review_row_to_dict(row) for row in rows])
    except Exception:
        logger.exception("_list_sqlite_memories failed for user=%s, falling back to DEMO_MEMORIES", user_id)
        return []


def _review_row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "error_type": row["error_type"],
        "knowledge_type": row["knowledge_type"],
        "knowledge_tags": _json_list(row["knowledge_tags"]),
        "mistake_summary": row["mistake_summary"],
        "review_tip": row["review_tip"],
        "remember_points": _json_list(row["remember_points"]),
        "understand_points": _json_list(row["understand_points"]),
        "common_mistakes": _json_list(row["common_mistakes"]),
        "session_id": row["session_id"],
        "problem_text": row["problem_text"],
        "user_code": row["user_code"],
        "memory_key": row["memory_key"],
        "question_key": row["question_key"] if "question_key" in row.keys() else "",
        "issue_type": row["issue_type"],
        "occurrence_count": row["occurrence_count"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "next_review_at": row["next_review_at"],
        "updated_at": row["updated_at"],
        "last_recalled_at": row["last_recalled_at"],
        "recall_count": row["recall_count"],
        "mastery": row["mastery"],
        "mastery_status": row["mastery_status"],
        "review_count": row["review_count"],
        "last_reviewed_at": row["last_reviewed_at"],
        "created_at": row["created_at"] if "created_at" in row.keys() else "",
    }


def _collapse_exact_question_duplicates(items: list[dict]) -> list[dict]:
    question_groups: dict[str, dict] = {}
    legacy_items: list[dict] = []
    for item in sorted(items, key=_memory_first_date):
        question_key = item.get("question_key") or build_question_key(
            item.get("user_id", ""),
            item.get("problem_text", ""),
            item.get("user_code", ""),
        )
        if not question_key:
            legacy_items.append(item)
            continue
        existing = question_groups.get(question_key)
        if existing:
            _merge_memory_summary(existing, item)
        else:
            question_groups[question_key] = {**item, "question_key": question_key}

    diagnostic_groups: dict[str, list[dict]] = {}
    for item in question_groups.values():
        diagnostic_key = _build_diagnostic_key(item)
        if diagnostic_key:
            diagnostic_groups.setdefault(diagnostic_key, []).append(item)

    unresolved_legacy: dict[str, dict] = {}
    passthrough: list[dict] = []
    for item in legacy_items:
        diagnostic_key = _build_diagnostic_key(item)
        source_matches = diagnostic_groups.get(diagnostic_key, [])
        if diagnostic_key and len(source_matches) == 1:
            _merge_memory_summary(source_matches[0], item)
            continue
        if not diagnostic_key:
            passthrough.append(item)
            continue
        existing = unresolved_legacy.get(diagnostic_key)
        if existing:
            _merge_memory_summary(existing, item)
        else:
            unresolved_legacy[diagnostic_key] = {**item}

    collapsed = [*question_groups.values(), *unresolved_legacy.values(), *passthrough]
    return sorted(collapsed, key=lambda value: value.get("last_seen_at") or value.get("created_at") or "", reverse=True)


def _memory_first_date(item: dict) -> str:
    return item.get("first_seen_at") or item.get("created_at") or item.get("last_seen_at") or ""


def _build_diagnostic_key(item: dict) -> str:
    title = _normalize_question_text(item.get("title", ""))
    mistake_summary = _normalize_question_text(item.get("mistake_summary", ""))
    if not title or not mistake_summary:
        return ""
    return f"{title}\n{mistake_summary}"


def _merge_memory_summary(target: dict, duplicate: dict) -> None:
    target["occurrence_count"] = int(target.get("occurrence_count", 0) or 0) + int(duplicate.get("occurrence_count", 0) or 0)
    target["recall_count"] = int(target.get("recall_count", 0) or 0) + int(duplicate.get("recall_count", 0) or 0)
    target["review_count"] = int(target.get("review_count", 0) or 0) + int(duplicate.get("review_count", 0) or 0)
    target["first_seen_at"] = _earliest_date(
        target.get("first_seen_at") or target.get("created_at", ""),
        duplicate.get("first_seen_at") or duplicate.get("created_at", ""),
    )
    target["last_seen_at"] = _latest_date(target.get("last_seen_at", ""), duplicate.get("last_seen_at", ""))
    target["updated_at"] = _latest_date(target.get("updated_at", ""), duplicate.get("updated_at", ""))
    target["last_recalled_at"] = _latest_date(target.get("last_recalled_at", ""), duplicate.get("last_recalled_at", ""))
    target["last_reviewed_at"] = _latest_date(target.get("last_reviewed_at", ""), duplicate.get("last_reviewed_at", ""))
    target["mastery"] = min(float(target.get("mastery", 0.3) or 0.3), float(duplicate.get("mastery", 0.3) or 0.3))


def _earliest_date(left: str, right: str) -> str:
    values = [value for value in [left, right] if value]
    return min(values) if values else ""


def _latest_date(left: str, right: str) -> str:
    values = [value for value in [left, right] if value]
    return max(values) if values else ""


def _json_list(raw_value: str) -> list[str]:
    try:
        value = json.loads(raw_value or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _find_memory_by_key(connection, user_id: str, memory_key: str):
    if not memory_key:
        return None
    return connection.execute(
        """
        SELECT id, mastery
        FROM review_cards
        WHERE user_id = ? AND memory_key = ?
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """,
        (user_id, memory_key),
    ).fetchone()


def _find_memory_by_question_key(connection, user_id: str, question_key: str):
    if not question_key:
        return None
    return connection.execute(
        """
        SELECT id, mastery
        FROM review_cards
        WHERE user_id = ? AND question_key = ?
        ORDER BY first_seen_at ASC, created_at ASC
        LIMIT 1
        """,
        (user_id, question_key),
    ).fetchone()


def _find_memory_by_exact_question(connection, user_id: str, problem_text: str, user_code: str):
    normalized_problem = _normalize_question_text(problem_text)
    normalized_code = _normalize_question_code(user_code)
    if not normalized_problem and not normalized_code:
        return None
    rows = connection.execute(
        """
        SELECT id, mastery, problem_text, user_code
        FROM review_cards
        WHERE user_id = ? AND (problem_text != '' OR user_code != '')
        ORDER BY first_seen_at ASC, created_at ASC
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        if _normalize_question_text(row["problem_text"]) == normalized_problem and _normalize_question_code(row["user_code"]) == normalized_code:
            return row
    return None


def _write_concept_wrong_counts(connection, user_id: str, tags: list[str], mastery: float, mastery_status: str, today: str) -> None:
    for tag in tags:
        concept_id = f"{user_id}_{tag}"
        connection.execute(
            """
            INSERT INTO concept_mastery (
                id, user_id, concept, wrong_count, review_count, mastery,
                mastery_score, mastery_status, last_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                wrong_count = wrong_count + 1,
                mastery = excluded.mastery,
                mastery_score = excluded.mastery_score,
                mastery_status = excluded.mastery_status,
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            """,
            (
                concept_id,
                user_id,
                tag,
                1,
                0,
                mastery,
                mastery,
                mastery_status,
                today,
                today,
            ),
        )


def _issue_type_from_review_card(review_card: ReviewCard) -> str:
    if review_card.id.startswith("review_"):
        return review_card.id.removeprefix("review_")
    return review_card.error_type or "unknown_issue"


def _review_card_from_memory(memory: dict) -> ReviewCard:
    knowledge_type = memory.get("knowledge_type")
    if knowledge_type not in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}:
        knowledge_type = "UNKNOWN"
    return ReviewCard(
        id=str(memory.get("id") or ""),
        title=str(memory.get("title") or ""),
        error_type=str(memory.get("error_type") or ""),
        knowledge_type=knowledge_type,
        knowledge_tags=[str(tag) for tag in memory.get("knowledge_tags", []) if str(tag)],
        mistake_summary=str(memory.get("mistake_summary") or ""),
        review_tip=str(memory.get("review_tip") or ""),
        remember_points=[str(item) for item in memory.get("remember_points", []) if str(item)],
        understand_points=[str(item) for item in memory.get("understand_points", []) if str(item)],
        common_mistakes=[str(item) for item in memory.get("common_mistakes", []) if str(item)],
        next_review_at=str(memory.get("next_review_at") or ""),
    )


def _record_memory_recall(user_id: str, memory_id: str) -> None:
    try:
        initialize_database()
        today = date.today().isoformat()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE review_cards
                SET recall_count = recall_count + 1, last_recalled_at = ?
                WHERE user_id = ? AND id = ?
                """,
                (today, user_id, memory_id),
            )
            connection.commit()
    except Exception:
        logger.warning("_record_memory_recall failed for memory=%s", memory_id, exc_info=True)


def _score_memory_match(query: str, item: dict) -> float:
    query_text = query.lower()
    haystack = f"{item['title']} {item['mistake_summary']} {item['review_tip']} {' '.join(item['knowledge_tags'])}".lower()
    token_pool = {
        "scanf",
        "数组",
        "二分",
        "边界",
        "循环",
        "变量",
        "初始化",
        "赋值",
        "比较",
        "条件",
        "取地址",
        "输入",
        "语法",
        "算法",
        "越界",
        "死循环",
    }
    token_pool.update(str(tag).lower() for tag in item.get("knowledge_tags", []) if len(str(tag)) >= 2)
    token_pool.update(str(word).lower() for word in item.get("title", "").split() if len(str(word)) >= 2)
    matched_tokens = [token for token in token_pool if token and token in query_text and token in haystack]
    if not matched_tokens:
        return 0.0
    strong_bonus = 0.25 if any(token in {"scanf", "数组", "二分", "取地址", "初始化", "赋值"} for token in matched_tokens) else 0.0
    base = min(len(matched_tokens) / 4, 0.75)
    return min(base + strong_bonus, 0.95)


def _normalize_question_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_question_code(value: str) -> str:
    without_line_comments = re.sub(r"//.*", "", value or "")
    without_block_comments = re.sub(r"/\*.*?\*/", "", without_line_comments, flags=re.S)
    return re.sub(r"\s+", "", without_block_comments).strip().lower()
