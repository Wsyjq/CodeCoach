import unicodedata
import time
from pathlib import Path

from app.config import settings


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
_llm_disabled_until = 0.0


SYSTEM_PROMPT = (
    "你是 CodeCoach，一个面向 C 语言初学者的刷题学习助手。"
    "你的目标是让学生知道自己为什么错、下一步该检查哪里、哪些规则需要复习。"
    "你需要区分记忆型知识和理解型知识，用新手能听懂的方式解释。"
    "除非用户明确要求，不要直接给完整题解代码或最终答案。"
)

RESPONSE_STYLE_GUIDE = (
    "\n\n统一输出风格：不用 emoji；不用复杂 Markdown；不要输出完整题解代码；"
    "先给一句话结论，再解释原因，再给最小下一步；语言口语化，适合 C 语言初学者；"
    "如果工具结果和模型判断冲突，以工具结果为准；不要编造题目、数据或历史记录。"
)

AGENT_SYSTEM_PROMPTS = {
    "Profile Agent": (
        "你是 CodeCoach 的 Profile Agent。你的任务是根据用户水平和输入内容，"
        "用一句话总结本次讲解应该采用的难度、语气和辅导重点。"
    ),
    "Intent Router": (
        "你是 CodeCoach 的 Intent Router。你的任务是把用户请求分类为一个意图标签。"
        "只能输出以下标签之一，不要输出解释、JSON 或标点："
        "KNOWLEDGE_QA、DATA_QA、DEBUG_CODE、NEED_HINT、REVIEW_SUMMARY、UNDERSTAND_PROBLEM。"
    ),
    "Code Analyzer": (
        "你是 CodeCoach 的 Code Analyzer。你的任务是根据本地规则命中的 C 语言错误，"
        "用一句话总结最主要的问题类型和学生该优先检查的位置。"
    ),
    "RAG Agent": (
        "你是 CodeCoach 的 RAG Agent。你的任务是根据检索到的知识片段，"
        "用一句话总结这些片段能支撑的教学重点；没有证据时说明命中不足。"
    ),
    "Debug Agent": (
        "你是 CodeCoach 的 Debug Agent。你的任务是解释 C 语言代码错误原因，"
        "给最小修改提示，不直接给完整答案。"
    ),
    "Tutor Agent": (
        "你是 CodeCoach 的 Tutor Agent。你的任务是用新手友好的方式解释 C 语言知识点，"
        "区分需要记忆的规则和需要理解的原因。"
    ),
    "DataQA Agent": (
        "你是 CodeCoach 的 DataQA Agent。你的任务是根据学习统计数据回答用户的问数问题，"
        "只基于给定数据做解释和建议。"
    ),
    "Hint Agent": (
        "你是 CodeCoach 的 Hint Agent。你的任务是分层给提示，先启发思路，"
        "不要直接给完整代码或最终答案。"
    ),
    "Problem Parser": (
        "你是 CodeCoach 的 Problem Parser。你的任务是把题目拆成输入、处理、输出、边界四部分。"
    ),
    "Review Agent": (
        "你是 CodeCoach 的 Review Agent。你的任务是生成复盘建议，帮助学生知道为什么错、下次如何避免。"
    ),
    "Memory Agent": (
        "你是 CodeCoach 的 Memory Agent。你的任务是根据历史错题记忆生成相似错误提醒，"
        "提醒要具体、简短、不过度打扰。"
    ),
    "Follow-up Agent": (
        "你是 CodeCoach 的 Follow-up Agent。你的任务是沿用同一会话上下文回答追问，"
        "不要把追问当成全新的问题。"
    ),
}

AGENT_PROMPT_FILES = {
    "Profile Agent": "profile.md",
    "Intent Router": "router.md",
    "Code Analyzer": "code_analyzer.md",
    "RAG Agent": "rag.md",
    "Debug Agent": "debug.md",
    "Tutor Agent": "tutor.md",
    "DataQA Agent": "data_qa.md",
    "Hint Agent": "hint.md",
    "Problem Parser": "problem_parser.md",
    "Review Agent": "review.md",
    "Memory Agent": "memory.md",
    "Follow-up Agent": "followup.md",
}


def is_llm_available() -> bool:
    return settings.use_llm and bool(settings.llm_api_key) and time.monotonic() >= _llm_disabled_until


def call_llm(user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str | None:
    if not is_llm_available():
        return None

    try:
        import httpx

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        with httpx.Client(base_url=settings.llm_base_url, timeout=settings.llm_timeout_seconds) as client:
            content = _create_completion(client, messages)
        return _clean_llm_content(content) if content else None
    except Exception:
        _open_llm_cooldown()
        return None


def _open_llm_cooldown() -> None:
    global _llm_disabled_until
    if settings.llm_failure_cooldown_seconds <= 0:
        _llm_disabled_until = 0.0
        return
    _llm_disabled_until = time.monotonic() + settings.llm_failure_cooldown_seconds


def call_agent_llm(agent_name: str, user_prompt: str) -> str | None:
    system_prompt = load_agent_prompt(agent_name)
    if agent_name != "Intent Router":
        system_prompt = f"{system_prompt}{RESPONSE_STYLE_GUIDE}"
    return call_llm(user_prompt=user_prompt, system_prompt=system_prompt)


def load_agent_prompt(agent_name: str) -> str:
    file_name = AGENT_PROMPT_FILES.get(agent_name)
    if not file_name:
        return AGENT_SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPT)
    path = PROMPT_DIR / file_name
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError:
        return AGENT_SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPT)
    return content or AGENT_SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPT)


def _create_completion(client, messages: list[dict]) -> str | None:
    response = client.post(
        "/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000,
        },
    )
    response.raise_for_status()
    data = response.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content")


def _clean_llm_content(content: str, max_chars: int = 300) -> str:
    cleaned = "".join(char for char in content.strip() if unicodedata.category(char) not in {"So", "Sk"})
    for marker in ["**", "###", "##", "---", "```"]:
        cleaned = cleaned.replace(marker, "")
    lines = [line.strip() for line in cleaned.splitlines()]
    compact_lines = [
        line.lstrip("-*").strip()
        for line in lines
        if line and not line.startswith("#")
    ]
    cleaned = "\n".join(compact_lines).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."
