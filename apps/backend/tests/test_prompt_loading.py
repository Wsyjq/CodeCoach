from app.agents import llm_backend


def test_load_agent_prompt_reads_markdown_file():
    prompt = llm_backend.load_agent_prompt("Debug Agent")

    assert "C 语言代码纠错教练" in prompt


def test_router_prompt_requires_single_intent_label():
    prompt = llm_backend.load_agent_prompt("Intent Router")

    assert "只输出一个标签" in prompt
    assert "不要输出 JSON" in prompt
    assert "DEBUG_CODE" in prompt


def test_load_agent_prompt_falls_back_for_unknown_agent():
    prompt = llm_backend.load_agent_prompt("Unknown Agent")

    assert prompt == llm_backend.SYSTEM_PROMPT


def test_load_agent_prompt_falls_back_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_backend, "PROMPT_DIR", tmp_path)

    prompt = llm_backend.load_agent_prompt("Debug Agent")

    assert prompt == llm_backend.AGENT_SYSTEM_PROMPTS["Debug Agent"]


def test_all_configured_agent_prompt_files_exist():
    missing = [
        file_name
        for file_name in llm_backend.AGENT_PROMPT_FILES.values()
        if not (llm_backend.PROMPT_DIR / file_name).exists()
    ]

    assert missing == []


def test_all_configured_agent_prompts_define_output_constraints():
    missing_output_rules = [
        agent_name
        for agent_name in llm_backend.AGENT_PROMPT_FILES
        if "输出" not in llm_backend.load_agent_prompt(agent_name)
    ]

    assert missing_output_rules == []


def test_call_agent_llm_appends_response_style_except_router(monkeypatch):
    calls = []

    def fake_call_llm(user_prompt: str, system_prompt: str):
        calls.append((user_prompt, system_prompt))
        return "ok"

    monkeypatch.setattr(llm_backend, "call_llm", fake_call_llm)

    assert llm_backend.call_agent_llm("Debug Agent", "用户问题") == "ok"
    assert "统一输出风格" in calls[-1][1]

    assert llm_backend.call_agent_llm("Intent Router", "用户问题") == "ok"
    assert "统一输出风格" not in calls[-1][1]
