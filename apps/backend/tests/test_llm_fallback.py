from app.agents import llm_backend, orchestrator
from app.config import settings
from app.schemas.chat import ChatRequest


def test_llm_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "use_llm", False)
    monkeypatch.setattr(settings, "llm_api_key", "fake-key")

    assert llm_backend.call_llm("hello") is None


def test_llm_enabled_without_key_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "")

    assert llm_backend.call_llm("hello") is None


def test_chat_falls_back_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "")

    response = orchestrator.handle_chat(ChatRequest(message="scanf 为什么要加 &？"))

    assert response.intent == "KNOWLEDGE_QA"
    assert response.answer
    assert response.agent_trace[0].detail == "beginner"


def test_router_falls_back_to_rule_intent_when_llm_output_invalid(monkeypatch):
    def fake_agent_llm(agent_name: str, user_prompt: str) -> str | None:
        if agent_name == "Intent Router":
            return "这不是一个合法意图"
        return None

    monkeypatch.setattr(orchestrator, "call_agent_llm", fake_agent_llm)

    response = orchestrator.handle_chat(
        ChatRequest(message="我这个代码为什么过不了？", code='int main(){ int n; scanf("%d", n); }')
    )

    assert response.intent == "DEBUG_CODE"
    assert response.review_card.id


def test_router_accepts_valid_llm_intent(monkeypatch):
    def fake_agent_llm(agent_name: str, user_prompt: str) -> str | None:
        if agent_name == "Intent Router":
            return "意图：NEED_HINT"
        return None

    monkeypatch.setattr(orchestrator, "call_agent_llm", fake_agent_llm)

    response = orchestrator.handle_chat(ChatRequest(message="scanf 为什么要加 &？"))

    assert response.intent == "NEED_HINT"


def test_llm_content_cleanup_removes_markdown_emoji_and_truncates():
    raw = "### 标题\n✅ **原因**：" + "scanf 需要地址。" * 80

    cleaned = llm_backend._clean_llm_content(raw)

    assert len(cleaned) <= 300
    assert "✅" not in cleaned
    assert "###" not in cleaned
    assert "**" not in cleaned


def test_llm_failure_opens_cooldown(monkeypatch):
    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "fake-key")
    monkeypatch.setattr(settings, "llm_failure_cooldown_seconds", 60)
    monkeypatch.setattr(llm_backend, "_llm_disabled_until", 0.0)

    def failing_completion(client, messages):
        raise RuntimeError("llm timeout")

    monkeypatch.setattr(llm_backend, "_create_completion", failing_completion)

    assert llm_backend.call_llm("hello") is None
    assert llm_backend.is_llm_available() is False


def test_llm_failure_does_not_disable_next_call_when_cooldown_is_zero(monkeypatch):
    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "fake-key")
    monkeypatch.setattr(settings, "llm_failure_cooldown_seconds", 0)
    monkeypatch.setattr(llm_backend, "_llm_disabled_until", 0.0)

    def failing_completion(client, messages):
        raise RuntimeError("llm timeout")

    monkeypatch.setattr(llm_backend, "_create_completion", failing_completion)

    assert llm_backend.call_llm("hello") is None
    assert llm_backend.is_llm_available() is True


def test_core_agent_trace_runs_when_trace_llm_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_trace_agents", False)

    response = orchestrator.handle_chat(
        ChatRequest(
            message="我这个代码为什么过不了？",
            problem_text="输入一个整数 n，输出 n。",
            code='int main(){ int n; scanf("%d", n); return 0; }',
            mode="debug",
            session_id="trace_llm_disabled",
        )
    )

    nodes = {item.node for item in response.agent_trace}
    assert response.intent == "DEBUG_CODE"
    assert response.review_card.id
    assert nodes >= {"Profile Agent", "Intent Router", "Code Analyzer", "RAG Agent", "Review Agent", "Memory Agent"}
