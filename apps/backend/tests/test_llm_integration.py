import os

import pytest
from dotenv import load_dotenv

from app.agents.llm_backend import call_agent_llm
from app.config import settings


def test_real_openai_compatible_llm_call_when_enabled(monkeypatch):
    load_dotenv()
    if os.getenv("CODECOACH_RUN_LLM_TESTS") != "true":
        pytest.skip("set CODECOACH_RUN_LLM_TESTS=true to call the real LLM")

    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        pytest.skip("LLM_API_KEY is not configured")

    monkeypatch.setattr(settings, "use_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", api_key)
    monkeypatch.setattr(settings, "llm_base_url", os.getenv("LLM_BASE_URL", settings.llm_base_url))
    monkeypatch.setattr(settings, "llm_model", os.getenv("LLM_MODEL", settings.llm_model))

    answer = call_agent_llm(
        "Tutor Agent",
        "请用两句话解释：C 语言 scanf 为什么读取普通 int 变量时通常要加 &？",
    )

    assert isinstance(answer, str)
    assert len(answer.strip()) > 0
