import base64

import pytest

from conftest import assert_chat_response_shape, assert_memory_item_shape, assert_stats_summary_shape


def _chat_payload(message: str, problem_text: str = "", code: str = "", mode: str = "auto", session_id: str = "test_session") -> dict:
    return {
        "user_id": "demo_user",
        "user_level": "beginner",
        "message": message,
        "problem_text": problem_text,
        "code": code,
        "mode": mode,
        "session_id": session_id,
    }


def _register_user(client, username: str, display_name: str = "Test User", password: str = "secret123") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "display_name": display_name, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers_are_set(client):
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"


def test_basic_auth_protects_api_when_configured(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "basic_auth_username", "admin")
    monkeypatch.setattr(settings, "basic_auth_password", "secret-password")
    credentials = base64.b64encode(b"admin:secret-password").decode("ascii")

    assert client.get("/health").status_code == 200
    assert client.get("/api/memories?user_id=demo_user").status_code == 401

    response = client.get(
        "/api/memories?user_id=demo_user",
        headers={"Authorization": f"Basic {credentials}"},
    )

    assert response.status_code == 200


def test_traces_can_be_hidden_for_public_deployments(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "expose_traces", False)

    response = client.get("/api/traces?user_id=demo_user")

    assert response.status_code == 404


def test_maintenance_mode_keeps_status_open_and_blocks_api(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "maintenance_mode", True)
    monkeypatch.setattr(settings, "maintenance_message", "维护中")

    status_response = client.get("/api/status")
    chat_response = client.post("/api/chat", json=_chat_payload(message="scanf 为什么要加 &？"))

    assert status_response.status_code == 200
    assert status_response.json() == {"status": "maintenance", "maintenance": True, "message": "维护中"}
    assert chat_response.status_code == 503
    assert chat_response.json() == {"detail": "维护中"}


def test_maintenance_status_message_can_be_empty(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "maintenance_mode", True)
    monkeypatch.setattr(settings, "maintenance_message", "")

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {"status": "maintenance", "maintenance": True, "message": ""}


def test_auth_register_login_and_me(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_required", True)

    register_data = _register_user(client, "student_a", display_name="Student A")

    assert register_data["token"]
    assert register_data["user"]["username"] == "student_a"
    assert register_data["user"]["display_name"] == "Student A"

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {register_data['token']}"})
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "student_a"

    login_response = client.post("/api/auth/login", json={"username": "student_a", "password": "secret123"})
    assert login_response.status_code == 200
    assert login_response.json()["token"]


def test_auth_rejects_duplicate_and_invalid_registration(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_required", True)
    _register_user(client, "student_dup")

    duplicate = client.post(
        "/api/auth/register",
        json={"username": "student_dup", "display_name": "Duplicate", "password": "secret123"},
    )
    invalid_username = client.post(
        "/api/auth/register",
        json={"username": "bad user", "display_name": "Bad", "password": "secret123"},
    )
    short_password = client.post(
        "/api/auth/register",
        json={"username": "student_short", "display_name": "Short", "password": "123"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Username already exists"
    assert invalid_username.status_code == 422
    assert short_password.status_code == 422


def test_learning_api_requires_valid_bearer_token_when_auth_required(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_required", True)

    assert client.get("/api/memories").status_code == 401
    assert client.get("/api/memories", headers={"Authorization": "Bearer fake-token"}).status_code == 401

    token = _register_user(client, "student_b")["token"]
    response = client.get("/api/memories", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_logout_invalidates_session_token(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_required", True)
    token = _register_user(client, "student_logout")["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get("/api/memories", headers=headers).status_code == 401


def test_user_id_input_cannot_access_another_users_learning_data(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_required", True)
    alice = _register_user(client, "alice_user", display_name="Alice")
    bob = _register_user(client, "bob_user", display_name="Bob")
    alice_headers = {"Authorization": f"Bearer {alice['token']}"}
    bob_headers = {"Authorization": f"Bearer {bob['token']}"}

    response = client.post(
        "/api/chat",
        json={
            **_chat_payload(
                message="我这个代码为什么过不了？",
                problem_text="输入一个整数 n，输出 n。",
                code='int main(){ int n; scanf("%d", n); return 0; }',
                mode="debug",
                session_id="alice_debug_session",
            ),
            "user_id": bob["user"]["id"],
        },
        headers=alice_headers,
    )
    assert response.status_code == 200
    memory_id = response.json()["review_card"]["id"]

    alice_memories = client.get(f"/api/memories?user_id={bob['user']['id']}", headers=alice_headers)
    bob_memories = client.get(f"/api/memories?user_id={alice['user']['id']}", headers=bob_headers)
    bob_review = client.post(
        f"/api/memories/{memory_id}/review",
        json={"user_id": alice["user"]["id"], "outcome": "reviewed"},
        headers=bob_headers,
    )

    assert alice_memories.status_code == 200
    assert [item["id"] for item in alice_memories.json()["items"]] == [memory_id]
    assert bob_memories.status_code == 200
    assert bob_memories.json() == {"items": []}
    assert bob_review.status_code == 404


def test_chat_debug_code_contract(client):
    response = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "DEBUG_CODE"
    assert data["review_card"]["id"]
    assert data["review_card"]["title"]
    assert data["review_card"]["error_type"]
    assert data["review_card"]["mistake_summary"]
    assert data["review_card"]["review_tip"]
    assert data["review_card"]["remember_points"]
    assert data["review_card"]["understand_points"]
    assert data["review_card"]["common_mistakes"]
    assert data["review_card"]["next_review_at"]
    assert {item["node"] for item in data["agent_trace"]} >= {"Profile Agent", "Intent Router", "Code Analyzer"}


def test_chat_debug_code_reuses_exact_same_question_without_new_memory(client):
    payload = _chat_payload(
        message="我这个代码为什么过不了？",
        problem_text="输入一个整数 n，输出 n。",
        code='int main(){ int n; scanf("%d", n); return 0; }',
        mode="debug",
        session_id="duplicate_question_first",
    )
    first = client.post("/api/chat", json=payload)
    assert first.status_code == 200
    first_data = first.json()
    first_count = len(client.get("/api/memories?user_id=demo_user").json()["items"])

    second_payload = dict(payload)
    second_payload["session_id"] = "duplicate_question_second"
    second = client.post("/api/chat", json=second_payload)

    assert second.status_code == 200
    data = second.json()
    assert_chat_response_shape(data)
    assert data["review_card"]["id"] == first_data["review_card"]["id"]
    assert data["similar_memory"]["matched"] is True
    assert data["similar_memory"]["exact_match"] is True
    assert data["similar_memory"]["first_seen_at"]
    assert "已经问过一模一样" in data["answer"]
    assert "不会" in data["answer"]
    assert len(client.get("/api/memories?user_id=demo_user").json()["items"]) == first_count
    assert "save_review_card" not in {
        item["tool_name"]
        for item in client.get("/api/traces?user_id=demo_user&session_id=duplicate_question_second").json()["items"]
    }


def test_chat_debug_code_without_rule_hit_does_not_save_review_card(client):
    session_id = "debug_no_rule_hit"
    before_memory_ids = {
        item["id"]
        for item in client.get("/api/memories?user_id=demo_user").json()["items"]
    }

    response = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n = 1; printf("%d", n); return 0; }',
            mode="debug",
            session_id=session_id,
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "DEBUG_CODE"
    assert data["review_card"]["id"] == ""
    assert "补充" in data["answer"]

    traces = client.get(f"/api/traces?user_id=demo_user&session_id={session_id}").json()["items"]
    assert "save_review_card" not in {item["tool_name"] for item in traces}

    after_memory_ids = {
        item["id"]
        for item in client.get("/api/memories?user_id=demo_user").json()["items"]
    }
    assert after_memory_ids == before_memory_ids


def test_chat_knowledge_qa_contract(client):
    response = client.post("/api/chat", json=_chat_payload(message="scanf 为什么要加 &？"))

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "KNOWLEDGE_QA"
    assert data["knowledge_tags"]


def test_chat_data_qa_contract(client):
    response = client.post("/api/chat", json=_chat_payload(message="我最近最常犯什么错误？"))

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "DATA_QA"


def test_chat_hint_contract(client):
    response = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我没思路，先别告诉答案，给点提示。",
            problem_text="输入 n 个整数，输出其中的最大值。",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "NEED_HINT"


def test_chat_review_summary_contract(client):
    response = client.post("/api/chat", json=_chat_payload(message="今天我应该复盘什么？"))

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "REVIEW_SUMMARY"


def test_chat_review_mode_generates_review_card_from_current_code(client):
    response = client.post(
        "/api/chat",
        json=_chat_payload(
            message="帮我生成本次错误复盘。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="review",
            session_id="review_current_code",
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "REVIEW_SUMMARY"
    assert data["review_card"]["id"].startswith("review_scanf_missing_address_")
    assert data["review_card"]["title"] == "scanf 输入错误"
    assert data["review_card"]["mistake_summary"]
    assert {item["node"] for item in data["agent_trace"]} >= {"Code Analyzer", "Review Agent", "Memory Agent"}


def test_chat_review_mode_reuses_latest_session_review_card(client):
    session_id = "review_from_session"
    before_count = len(client.get("/api/memories?user_id=demo_user").json()["items"])
    first = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="debug",
            session_id=session_id,
        ),
    )
    assert first.status_code == 200
    first_data = first.json()
    after_debug_memories = client.get("/api/memories?user_id=demo_user").json()["items"]
    assert len(after_debug_memories) == before_count
    assert sum(item["occurrence_count"] for item in after_debug_memories if item["title"] == "scanf 输入错误") == 2

    second = client.post(
        "/api/chat",
        json=_chat_payload(
            message="帮我生成本次错误复盘。",
            mode="review",
            session_id=session_id,
        ),
    )

    assert second.status_code == 200
    data = second.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "REVIEW_SUMMARY"
    assert data["review_card"]["id"] == first_data["review_card"]["id"]
    assert data["review_card"]["title"] == first_data["review_card"]["title"]
    assert "保存到错题本" in data["answer"]
    assert "不会重复新增" in data["answer"]
    assert {item["node"] for item in data["agent_trace"]} >= {"Session Memory", "Review Agent", "Memory Agent"}
    assert any(item["detail"] == "session review card reused" for item in data["agent_trace"])

    after_review_memories = client.get("/api/memories?user_id=demo_user").json()["items"]
    assert len(after_review_memories) == len(after_debug_memories)

    second_traces = client.get(f"/api/traces?user_id=demo_user&session_id={session_id}&turn_id={data['turn_id']}").json()["items"]
    assert "save_review_card" not in {item["tool_name"] for item in second_traces}


def test_chat_review_mode_without_code_context_does_not_save_card(client):
    session_id = "review_without_code_context"
    before_memory_ids = {
        item["id"]
        for item in client.get("/api/memories?user_id=demo_user").json()["items"]
    }

    response = client.post(
        "/api/chat",
        json=_chat_payload(
            message="帮我生成本次错误复盘。",
            mode="review",
            session_id=session_id,
        ),
    )

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "REVIEW_SUMMARY"
    assert data["review_card"]["id"] == ""
    assert "当前会话没有可复盘的代码" in data["answer"]
    assert "请先完成一次代码纠错" in data["answer"]
    assert any(item["detail"] == "no code context for review" for item in data["agent_trace"])

    after_memory_ids = {
        item["id"]
        for item in client.get("/api/memories?user_id=demo_user").json()["items"]
    }
    assert after_memory_ids == before_memory_ids

    traces = client.get(f"/api/traces?user_id=demo_user&session_id={session_id}&turn_id={data['turn_id']}").json()["items"]
    assert "save_review_card" not in {item["tool_name"] for item in traces}


def test_chat_understand_problem_contract(client):
    response = client.post(
        "/api/chat",
        json=_chat_payload(message="题目什么意思？", problem_text="输入两个整数，输出它们的和。"),
    )

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == "UNDERSTAND_PROBLEM"


@pytest.mark.parametrize(
    ("mode", "expected_intent"),
    [
        ("knowledge", "KNOWLEDGE_QA"),
        ("debug", "DEBUG_CODE"),
        ("data", "DATA_QA"),
        ("hint", "NEED_HINT"),
        ("problem", "UNDERSTAND_PROBLEM"),
        ("review", "REVIEW_SUMMARY"),
    ],
)
def test_chat_mode_overrides_keyword_router(client, mode: str, expected_intent: str):
    payload = _chat_payload(
        message="我最近最常犯什么错误？",
        problem_text="输入一个整数 n，输出 n。",
        code='int main(){ int n; scanf("%d", n); return 0; }',
        mode=mode,
        session_id=f"mode_{mode}",
    )

    response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert_chat_response_shape(data)
    assert data["intent"] == expected_intent
    assert data["is_follow_up"] is False


def test_chat_followup_reuses_session_context(client):
    session_id = "followup_session"
    first = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="debug",
            session_id=session_id,
        ),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/chat",
        json=_chat_payload(
            message="为什么普通变量要传地址？",
            mode="followup",
            session_id=session_id,
        ),
    )

    assert second.status_code == 200
    data = second.json()
    assert_chat_response_shape(data)
    assert data["session_id"] == session_id
    assert data["is_follow_up"] is True
    assert data["conversation_title"] == first.json()["conversation_title"]
    assert {item["node"] for item in data["agent_trace"]} >= {"Session Memory", "Follow-up Agent"}


@pytest.mark.parametrize(
    "message",
    [
        "为什么 scanf 要加 &？",
        "再讲一下 scanf 的规则。",
        "举例说明数组下标为什么从 0 开始。",
        "这里我不懂，for 循环第三段是什么意思？",
    ],
)
def test_auto_mode_question_with_followup_words_is_not_forced_followup(client, message: str):
    session_id = f"auto_not_forced_followup_{abs(hash(message))}"
    first = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="debug",
            session_id=session_id,
        ),
    )
    assert first.status_code == 200

    second = client.post(
        "/api/chat",
        json=_chat_payload(
            message=message,
            mode="auto",
            session_id=session_id,
        ),
    )

    assert second.status_code == 200
    data = second.json()
    assert_chat_response_shape(data)
    assert data["is_follow_up"] is False
    assert "Follow-up Agent" not in {item["node"] for item in data["agent_trace"]}


def test_memories_contract(client):
    response = client.get("/api/memories?user_id=demo_user")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)
    assert data["items"]
    for item in data["items"]:
        assert_memory_item_shape(item)


def test_memory_detail_contract(client):
    list_response = client.get("/api/memories?user_id=demo_user")
    memory_id = list_response.json()["items"][0]["id"]

    response = client.get(f"/api/memories/{memory_id}?user_id=demo_user")

    assert response.status_code == 200
    assert_memory_item_shape(response.json())


def test_memory_detail_returns_404_for_missing_id(client):
    response = client.get("/api/memories/missing_id?user_id=demo_user")

    assert response.status_code == 404


def test_review_memory_updates_status(client):
    list_response = client.get("/api/memories?user_id=demo_user")
    memory_id = list_response.json()["items"][0]["id"]

    response = client.post(
        f"/api/memories/{memory_id}/review",
        json={"user_id": "demo_user", "outcome": "mastered"},
    )

    assert response.status_code == 200
    data = response.json()
    assert_memory_item_shape(data)
    assert data["mastery_status"] == "mastered"
    assert data["mastery"] >= 0.9

    due_response = client.get("/api/reviews/due?user_id=demo_user")
    assert all(item["id"] != memory_id for item in due_response.json()["due_reviews"])


def test_stats_summary_contract(client):
    response = client.get("/api/stats/summary?user_id=demo_user")

    assert response.status_code == 200
    assert_stats_summary_shape(response.json())


def test_reviews_due_contract(client):
    response = client.get("/api/reviews/due?user_id=demo_user&limit=2&status=reviewing")

    assert response.status_code == 200
    data = response.json()
    assert data["metric"] == "today_review"
    assert isinstance(data["time_range"], str)
    assert isinstance(data["target_date"], str)
    assert isinstance(data["due_count"], int)
    assert isinstance(data["due_reviews"], list)
    assert len(data["due_reviews"]) <= 2
    assert isinstance(data["recommended_actions"], list)
    for item in data["due_reviews"]:
        assert isinstance(item["id"], str)
        assert isinstance(item["title"], str)
        assert isinstance(item["error_type"], str)
        assert item["knowledge_type"] in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}
        assert isinstance(item["knowledge_tags"], list)
        assert isinstance(item["mistake_summary"], str)
        assert isinstance(item["review_tip"], str)
        assert isinstance(item["next_review_at"], str)
        assert isinstance(item["mastery"], float)
        assert item["mastery_status"] == "reviewing"


def test_knowledge_sources_contract(client):
    response = client.get("/api/knowledge/sources")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["total_cards"], int)
    assert isinstance(data["categories"], list)
    assert isinstance(data["sources"], list)
    for source in data["sources"]:
        assert isinstance(source["name"], str)
        assert isinstance(source["license"], str)
        assert isinstance(source["description"], str)


def test_tool_traces_contract(client):
    session_id = "trace_session"
    chat_response = client.post(
        "/api/chat",
        json=_chat_payload(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="debug",
            session_id=session_id,
        ),
    )
    assert chat_response.status_code == 200

    response = client.get(f"/api/traces?user_id=demo_user&session_id={session_id}")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    tool_names = {item["tool_name"] for item in items}
    assert {"analyze_c_code_light", "search_knowledge_base", "search_learning_memory", "save_review_card"}.issubset(tool_names)
    for item in items:
        assert item["session_id"] == session_id
        assert item["status"] in {"done", "warning", "error"}
