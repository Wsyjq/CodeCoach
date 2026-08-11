import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_backend(monkeypatch, tmp_path):
    from app.config import settings
    from app.db import database

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "codecoach_test.db")
    monkeypatch.setattr(settings, "use_llm", False)
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "auth_required", False)


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def assert_agent_trace_shape(agent_trace: list[dict]) -> None:
    assert agent_trace
    for item in agent_trace:
        assert isinstance(item["node"], str)
        assert item["status"] in {"waiting", "running", "done", "warning", "error"}
        assert isinstance(item["detail"], str)


def assert_chat_response_shape(data: dict) -> None:
    assert isinstance(data["session_id"], str)
    assert data["session_id"]
    assert isinstance(data["turn_id"], str)
    assert data["turn_id"]
    assert isinstance(data["is_follow_up"], bool)
    assert isinstance(data["conversation_title"], str)
    assert data["conversation_title"]
    assert isinstance(data["answer"], str)
    assert data["answer"]
    assert data["intent"] in {
        "KNOWLEDGE_QA",
        "DATA_QA",
        "DEBUG_CODE",
        "NEED_HINT",
        "REVIEW_SUMMARY",
        "UNDERSTAND_PROBLEM",
    }
    assert data["knowledge_type"] in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}
    assert isinstance(data["knowledge_tags"], list)
    assert isinstance(data["similar_memory"], dict)
    assert isinstance(data["similar_memory"]["matched"], bool)
    assert isinstance(data["similar_memory"]["mistake_summary"], str)
    assert isinstance(data["similar_memory"]["review_tip"], str)
    assert isinstance(data["similar_memory"]["score"], float)
    assert isinstance(data["review_card"], dict)
    assert isinstance(data["review_card"]["id"], str)
    assert isinstance(data["review_card"]["title"], str)
    assert isinstance(data["review_card"]["error_type"], str)
    assert data["review_card"]["knowledge_type"] in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}
    assert isinstance(data["review_card"]["knowledge_tags"], list)
    assert isinstance(data["review_card"]["mistake_summary"], str)
    assert isinstance(data["review_card"]["review_tip"], str)
    assert isinstance(data["review_card"]["remember_points"], list)
    assert isinstance(data["review_card"]["understand_points"], list)
    assert isinstance(data["review_card"]["common_mistakes"], list)
    assert isinstance(data["review_card"]["next_review_at"], str)
    assert isinstance(data["next_actions"], list)
    assert data["next_actions"]
    for action in data["next_actions"]:
        assert isinstance(action["label"], str)
        assert isinstance(action["message"], str)
        assert action["mode"] in {"followup", "review"}
    assert isinstance(data["agent_trace"], list)
    assert_agent_trace_shape(data["agent_trace"])


def assert_memory_item_shape(item: dict) -> None:
    assert isinstance(item["id"], str)
    assert isinstance(item["title"], str)
    assert isinstance(item["error_type"], str)
    assert item["knowledge_type"] in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}
    assert isinstance(item["knowledge_tags"], list)
    assert isinstance(item["mistake_summary"], str)
    assert isinstance(item["review_tip"], str)
    assert isinstance(item["remember_points"], list)
    assert isinstance(item["understand_points"], list)
    assert isinstance(item["common_mistakes"], list)
    assert isinstance(item["last_seen_at"], str)
    assert isinstance(item["next_review_at"], str)
    assert isinstance(item["mastery"], float)
    assert isinstance(item["mastery_status"], str)


def assert_stats_summary_shape(data: dict) -> None:
    assert isinstance(data["metric"], str)
    assert isinstance(data["time_range"], str)
    assert isinstance(data["total_records"], int)
    assert isinstance(data["top_errors"], list)
    assert isinstance(data["weak_tags"], list)
    assert isinstance(data["weak_concepts"], list)
    assert isinstance(data["review_due_count"], int)
    assert isinstance(data["due_reviews"], list)
    assert isinstance(data["recent_reviews"], list)
    assert isinstance(data["mastery_avg"], float)
    assert isinstance(data["recommended_actions"], list)
    for item in data["top_errors"]:
        assert isinstance(item["error_type"], str)
        assert isinstance(item["count"], int)
