from datetime import date, timedelta

from app.agents.orchestrator import handle_chat
from app.db.database import get_connection, initialize_database
from app.db.seed import seed_demo_data
from app.schemas.chat import ChatRequest, ReviewCard
from app.tools import memory_tool
from app.tools.memory_tool import find_exact_question_memory, list_demo_memories, reindex_learning_memories, save_review_card, search_learning_memory
from app.tools.session_tool import load_session_context
from app.tools.stats_tool import query_learning_stats


def test_seed_demo_memories_from_sqlite():
    memories = list_demo_memories("demo_user")

    assert len(memories) == 3
    assert {item["id"] for item in memories} >= {"review_001", "review_002", "review_003"}


def test_seed_demo_data_is_idempotent():
    seed_demo_data()
    seed_demo_data()

    assert len(list_demo_memories("demo_user")) == 3


def test_initialize_database_creates_tables():
    initialize_database()

    with get_connection() as connection:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        review_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(review_cards)").fetchall()
        }
        chat_log_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(chat_logs)").fetchall()
        }
        review_event_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(review_events)").fetchall()
        }
    assert {"review_cards", "concept_mastery", "chat_logs", "tool_traces", "review_events"}.issubset(table_names)
    assert {
        "knowledge_type",
        "remember_points",
        "understand_points",
        "common_mistakes",
        "memory_key",
        "issue_type",
        "occurrence_count",
        "first_seen_at",
        "updated_at",
        "last_recalled_at",
        "recall_count",
        "mastery_status",
        "review_count",
        "last_reviewed_at",
    }.issubset(review_columns)
    assert {"session_id", "turn_id", "role", "problem_text", "code", "context_json"}.issubset(chat_log_columns)
    assert {"memory_id", "outcome", "mastery_before", "mastery_after", "next_review_at"}.issubset(review_event_columns)


def test_debug_chat_saves_review_card():
    before = list_demo_memories("demo_user")

    response = handle_chat(ChatRequest(message="错", code='int main(){ int n; scanf("%d", n); return 0; }'))
    after = list_demo_memories("demo_user")

    assert response.intent == "DEBUG_CODE"
    assert response.review_card.id.startswith("review_scanf_missing_address_")
    assert response.review_card.mistake_summary
    assert response.review_card.remember_points
    assert response.review_card.understand_points
    assert response.review_card.common_mistakes
    assert len(after) == len(before)
    scanf_memory = next(item for item in after if item["title"] == "scanf 输入错误")
    assert scanf_memory["occurrence_count"] == 2


def test_chat_writes_session_context():
    response = handle_chat(
        ChatRequest(
            message="错",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="debug",
            session_id="unit_session",
        )
    )

    context = load_session_context("demo_user", "unit_session")

    assert response.session_id == "unit_session"
    assert response.turn_id
    assert len(context) == 2
    assert {item["role"] for item in context} == {"user", "assistant"}
    assert context[-1]["context"]["conversation_title"] == response.conversation_title


def test_memories_include_saved_review():
    response = handle_chat(ChatRequest(message="错", code='int main(){ int n; scanf("%d", n); return 0; }'))

    memories = list_demo_memories("demo_user")

    assert any(item["id"] == response.review_card.id for item in memories)


def test_stats_summary_reflects_saved_review():
    before = query_learning_stats("demo_user", "common_errors")

    handle_chat(ChatRequest(message="错", code='int main(){ int n; scanf("%d", n); return 0; }'))
    after = query_learning_stats("demo_user", "common_errors")

    assert after["total_records"] == before["total_records"]
    assert after["top_errors"]
    assert after["weak_tags"]


def test_today_review_returns_due_reviews():
    stats = query_learning_stats("demo_user", "today_review", time_range="today", limit=1, status="reviewing")

    assert stats["metric"] == "today_review"
    assert stats["time_range"] == "today"
    assert stats["due_reviews"]
    assert len(stats["due_reviews"]) == 1
    assert stats["due_reviews"][0]["mastery_status"] == "reviewing"
    assert stats["recommended_actions"]


def test_error_type_ratio_uses_persisted_records():
    stats = query_learning_stats("demo_user", "error_type_ratio")

    assert stats["metric"] == "error_type_ratio"
    assert stats["total_records"] == 3
    assert isinstance(stats["syntax_errors"], int)
    assert isinstance(stats["algorithm_errors"], int)
    assert isinstance(stats["boundary_errors"], int)
    assert isinstance(stats["syntax_ratio"], float)
    assert isinstance(stats["algorithm_ratio"], float)
    assert isinstance(stats["boundary_ratio"], float)
    assert stats["recommended_actions"]


def test_concept_attempt_count_uses_persisted_records():
    stats = query_learning_stats("demo_user", "concept_attempt_count", query="二分查找错过几次")

    assert stats["metric"] == "concept_attempt_count"
    assert stats["concept"] == "二分查找"
    assert stats["count"] == 1
    assert stats["recent_reviews"]
    assert stats["recommended_actions"]


def test_weak_concepts_metric_uses_review_tags():
    stats = query_learning_stats("demo_user", "weak_concepts")

    assert stats["metric"] == "weak_concepts"
    assert stats["weak_concepts"]
    assert stats["weak_tags"]
    assert stats["recommended_actions"]


def test_last_similar_mistake_metric_uses_memory_similarity():
    stats = query_learning_stats("demo_user", "last_similar_mistake", query='scanf("%d", n)')

    assert stats["metric"] == "last_similar_mistake"
    assert stats["similar_memory"]["matched"] is True
    assert stats["similar_memory"]["title"] == "scanf 输入错误"
    assert stats["recommended_actions"]


def test_save_review_card_indexes_learning_memory(monkeypatch):
    calls = []

    def fake_upsert(collection_name, ids, documents, metadatas):
        calls.append((collection_name, ids, documents, metadatas))
        return True

    monkeypatch.setattr(memory_tool, "upsert_documents", fake_upsert)

    saved = save_review_card(
        user_id="demo_user",
        review_card=ReviewCard(
            id="review_vector",
            title="向量复盘",
            error_type="C语法错误",
            knowledge_type="MEMORIZE",
            knowledge_tags=["C语言", "scanf"],
            mistake_summary="测试向量写入。",
            review_tip="测试向量召回。",
            remember_points=["测试记忆点"],
            understand_points=["测试理解点"],
            common_mistakes=["测试易错点"],
        ),
    )

    assert saved.id.startswith("review_vector_")
    assert calls
    collection_name, ids, documents, metadatas = calls[0]
    assert collection_name == memory_tool.COLLECTION_MEMORIES
    assert ids == [saved.id]
    assert "向量复盘" in documents[0]
    assert metadatas[0]["user_id"] == "demo_user"
    assert metadatas[0]["memory_key"]
    assert metadatas[0]["mastery_status"] == "reviewing"


def test_save_review_card_merges_same_memory_key(monkeypatch):
    monkeypatch.setattr(memory_tool, "upsert_documents", lambda *args, **kwargs: True)
    review = ReviewCard(
        id="review_scanf_missing_address",
        title="scanf 输入错误",
        error_type="C语法错误",
        knowledge_type="MEMORIZE",
        knowledge_tags=["C语言", "scanf", "取地址"],
        mistake_summary="忘记给普通变量加 &。",
        review_tip="检查 scanf 参数是否是地址。",
        remember_points=["普通变量输入要加 &"],
        understand_points=["scanf 需要地址写回变量"],
        common_mistakes=["scanf(\"%d\", n)"],
    )

    first = save_review_card("merge_user", review, issue_type="scanf_missing_address")
    second = save_review_card("merge_user", review, issue_type="scanf_missing_address")
    memories = list_demo_memories("merge_user")

    assert first.id == second.id
    assert len(memories) == 1
    assert memories[0]["occurrence_count"] == 2
    assert memories[0]["memory_key"].startswith("merge_user:scanf_missing_address:")


def test_save_review_card_reuses_exact_same_question(monkeypatch):
    monkeypatch.setattr(memory_tool, "upsert_documents", lambda *args, **kwargs: True)
    problem_text = "输入一个整数 n，输出 n。"
    user_code = 'int main(){ int n; scanf("%d", n); return 0; }'
    review = ReviewCard(
        id="review_scanf_missing_address",
        title="scanf 输入错误",
        error_type="C语法错误",
        knowledge_type="MEMORIZE",
        knowledge_tags=["C语言", "scanf", "输入"],
        mistake_summary="忘记给普通变量加 &。",
        review_tip="检查 scanf 参数是否是地址。",
        remember_points=["普通变量输入要加 &"],
        understand_points=["scanf 需要地址写回变量"],
        common_mistakes=["scanf(\"%d\", n)"],
    )

    first = save_review_card("exact_user", review, problem_text=problem_text, user_code=user_code, issue_type="scanf_missing_address")
    second = save_review_card(
        "exact_user",
        review,
        problem_text="输入一个整数 n，输出 n。",
        user_code='int main(){int n;scanf("%d",n);return 0;}',
        issue_type="scanf_missing_address",
    )
    memories = list_demo_memories("exact_user")
    exact = find_exact_question_memory("exact_user", problem_text, user_code)

    assert first.id == second.id
    assert len(memories) == 1
    assert memories[0]["occurrence_count"] == 2
    assert memories[0]["question_key"]
    assert exact is not None
    assert exact["id"] == first.id


def test_list_memories_collapses_legacy_exact_question_duplicates():
    initialize_database()
    problem_text = "输入一个整数 n，输出 n。"
    user_code = 'int main(){ int n; scanf("%d", n); return 0; }'
    with get_connection() as connection:
        for index, seen_at in enumerate(["2026-07-08", "2026-07-11"], start=1):
            connection.execute(
                """
                INSERT INTO review_cards (
                    id, user_id, title, problem_text, user_code, error_type,
                    knowledge_type, knowledge_tags, mistake_summary, review_tip,
                    remember_points, understand_points, common_mistakes,
                    first_seen_at, last_seen_at, next_review_at, mastery, occurrence_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"legacy_duplicate_{index}",
                    "legacy_user",
                    "scanf 输入错误",
                    problem_text,
                    user_code,
                    "C语法错误",
                    "MEMORIZE",
                    '["C语言", "scanf"]',
                    "忘记给普通变量加 &。",
                    "检查 scanf 参数是否是地址。",
                    '["普通变量输入要加 &"]',
                    '["scanf 需要地址写回变量"]',
                    '["scanf(\\"%d\\", n)"]',
                    seen_at,
                    seen_at,
                    "2026-07-12",
                    0.3,
                    index,
                    seen_at,
                ),
            )
        connection.commit()

    memories = list_demo_memories("legacy_user")

    assert len(memories) == 1
    assert memories[0]["occurrence_count"] == 3
    assert memories[0]["first_seen_at"] == "2026-07-08"
    assert memories[0]["last_seen_at"] == "2026-07-11"


def test_list_memories_attaches_sourceless_legacy_card_to_matching_question():
    initialize_database()
    shared_values = (
        "legacy_match_user",
        "scanf 输入错误",
        "C语法错误",
        "MEMORIZE",
        '["C语言", "scanf"]',
        "用户在 scanf 中忘记给普通变量加 &。",
        "读取普通变量时通常要传变量地址。",
    )
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO review_cards (
                id, user_id, title, error_type, knowledge_type, knowledge_tags,
                mistake_summary, review_tip, problem_text, user_code,
                occurrence_count, review_count, last_seen_at, next_review_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', '', 1, 2, '2026-07-09', '2026-07-12', '2026-07-08')
            """,
            ("legacy_sourceless", *shared_values),
        )
        connection.execute(
            """
            INSERT INTO review_cards (
                id, user_id, title, error_type, knowledge_type, knowledge_tags,
                mistake_summary, review_tip, problem_text, user_code,
                occurrence_count, review_count, first_seen_at, last_seen_at, next_review_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 2, 1, '2026-07-09', '2026-07-11', '2026-07-12', '2026-07-09')
            """,
            (
                "real_question",
                *shared_values,
                "输入一个整数 n，输出 n。",
                'int main(){int n; scanf("%d", n);}',
            ),
        )
        connection.commit()

    memories = list_demo_memories("legacy_match_user")

    assert len(memories) == 1
    assert memories[0]["id"] == "real_question"
    assert memories[0]["occurrence_count"] == 3
    assert memories[0]["review_count"] == 3
    assert memories[0]["first_seen_at"] == "2026-07-08"
    assert memories[0]["last_seen_at"] == "2026-07-11"


def test_save_review_card_creates_new_memory_for_different_issue(monkeypatch):
    monkeypatch.setattr(memory_tool, "upsert_documents", lambda *args, **kwargs: True)

    first = save_review_card(
        "issue_user",
        ReviewCard(
            id="review_scanf_missing_address",
            title="scanf 输入错误",
            error_type="C语法错误",
            knowledge_type="MEMORIZE",
            knowledge_tags=["C语言", "scanf"],
            mistake_summary="忘记 &。",
            review_tip="检查地址。",
        ),
        issue_type="scanf_missing_address",
    )
    second = save_review_card(
        "issue_user",
        ReviewCard(
            id="review_loop_update_missing",
            title="循环变量未更新",
            error_type="循环边界错误",
            knowledge_type="UNDERSTAND",
            knowledge_tags=["C语言", "循环"],
            mistake_summary="循环变量没有推进。",
            review_tip="检查 for 第三段。",
        ),
        issue_type="loop_update_missing",
    )

    assert first.id != second.id
    assert len(list_demo_memories("issue_user")) == 2


def test_reindex_learning_memories_indexes_sqlite_cards(monkeypatch):
    calls = []

    def fake_upsert(collection_name, ids, documents, metadatas):
        calls.append((collection_name, ids, documents, metadatas))
        return True

    monkeypatch.setattr(memory_tool, "upsert_documents", fake_upsert)
    save_review_card(
        "reindex_user",
        ReviewCard(
            id="review_reindex",
            title="重建索引复盘",
            error_type="C语法错误",
            knowledge_type="MEMORIZE",
            knowledge_tags=["C语言"],
            mistake_summary="测试重建。",
            review_tip="测试建议。",
        ),
    )

    calls.clear()
    result = reindex_learning_memories("reindex_user")

    assert result == {"indexed_count": 1, "failed_count": 0}
    assert calls
    assert calls[0][0] == memory_tool.COLLECTION_MEMORIES


def test_search_learning_memory_prefers_vector_result(monkeypatch):
    def fake_search(collection_name, query, top_k=1, where=None):
        return [
            {
                "id": "vector_review",
                "document": "scanf 向量命中",
                "metadata": {
                    "title": "向量 scanf 错题",
                    "mistake_summary": "向量命中错因。",
                    "review_tip": "向量复习建议。",
                },
                "score": 0.88,
            }
        ]

    monkeypatch.setattr(memory_tool, "search_similar", fake_search)

    result = search_learning_memory("demo_user", 'scanf("%d", n)')

    assert result.matched is True
    assert result.title == "向量 scanf 错题"
    assert result.score == 0.88


def test_memory_similarity_recalls_scanf_review():
    before = list_demo_memories("demo_user")[0]["recall_count"]

    result = search_learning_memory("demo_user", 'scanf("%d", n) 忘记加地址')

    assert result.matched is True
    assert result.title
    assert result.mistake_summary
    assert result.review_tip
    assert result.score > 0
    after = next(item for item in list_demo_memories("demo_user") if item["title"] == result.title)
    assert after["recall_count"] == before + 1
    assert after["last_recalled_at"]


def test_memory_similarity_returns_false_for_unrelated_query():
    result = search_learning_memory("demo_user", "今天食堂午饭吃什么")

    assert result.matched is False


def test_save_review_card_writes_concept_mastery():
    saved = save_review_card(
        user_id="demo_user",
        review_card=ReviewCard(
            id="review_custom",
            title="自定义复盘",
            error_type="C语法错误",
            knowledge_type="MEMORIZE",
            knowledge_tags=["C语言", "变量"],
            mistake_summary="测试复盘写入。",
            review_tip="测试掌握度更新。",
            remember_points=["变量使用前要先赋值"],
            understand_points=["未初始化变量的值不可预测"],
            common_mistakes=["声明后直接输出变量"],
            next_review_at="2026-07-09",
        ),
        knowledge_tags=["C语言", "变量"],
        mistake_summary="测试复盘写入。",
        review_tip="测试掌握度更新。",
    )

    with get_connection() as connection:
        concepts = connection.execute(
            "SELECT concept FROM concept_mastery WHERE user_id = ?",
            ("demo_user",),
        ).fetchall()

    assert saved.id.startswith("review_custom_")
    assert saved.remember_points == ["变量使用前要先赋值"]
    assert saved.understand_points == ["未初始化变量的值不可预测"]
    assert saved.common_mistakes == ["声明后直接输出变量"]
    assert {row["concept"] for row in concepts} >= {"C语言", "变量"}


def test_mark_memory_reviewed_updates_mastery_and_concepts():
    memory = list_demo_memories("demo_user")[0]

    updated = memory_tool.mark_memory_reviewed("demo_user", memory["id"], "mastered")

    assert updated is not None
    assert updated["mastery_status"] == "mastered"
    assert updated["mastery"] >= 0.9
    assert updated["review_count"] == 1
    assert updated["last_reviewed_at"]

    with get_connection() as connection:
        event = connection.execute(
            "SELECT outcome, mastery_before, mastery_after, next_review_at FROM review_events WHERE memory_id = ?",
            (memory["id"],),
        ).fetchone()
    assert event is not None
    assert event["outcome"] == "mastered"
    assert event["mastery_before"] == memory["mastery"]
    assert event["mastery_after"] == updated["mastery"]
    assert event["next_review_at"] == updated["next_review_at"]

    due = query_learning_stats("demo_user", "today_review")
    assert all(item["id"] != memory["id"] for item in due["due_reviews"])


def test_mark_memory_reviewed_again_keeps_card_reviewing_and_schedules_tomorrow():
    memory = list_demo_memories("demo_user")[0]

    updated = memory_tool.mark_memory_reviewed("demo_user", memory["id"], "again")

    assert updated is not None
    assert updated["mastery_status"] == "reviewing"
    assert updated["mastery"] < memory["mastery"]
    assert updated["next_review_at"] == (date.today() + timedelta(days=1)).isoformat()
    assert updated["review_count"] == 1
    assert updated["last_reviewed_at"]

    with get_connection() as connection:
        event = connection.execute(
            "SELECT outcome, mastery_before, mastery_after, next_review_at FROM review_events WHERE memory_id = ?",
            (memory["id"],),
        ).fetchone()

    assert event is not None
    assert event["outcome"] == "again"
    assert event["mastery_before"] == memory["mastery"]
    assert event["mastery_after"] == updated["mastery"]
    assert event["next_review_at"] == updated["next_review_at"]
