from app.schemas.chat import ChatRequest, Intent


MODE_INTENTS: dict[str, Intent] = {
    "knowledge": "KNOWLEDGE_QA",
    "problem": "UNDERSTAND_PROBLEM",
    "hint": "NEED_HINT",
    "debug": "DEBUG_CODE",
    "data": "DATA_QA",
    "review": "REVIEW_SUMMARY",
}


def intent_from_mode(mode: str) -> Intent | None:
    normalized = (mode or "auto").strip().lower()
    if normalized in {"auto", "followup"}:
        return None
    return MODE_INTENTS.get(normalized)


def route_intent(request: ChatRequest) -> Intent:
    mode_intent = intent_from_mode(request.mode)
    if mode_intent:
        return mode_intent

    text = f"{request.message}\n{request.problem_text}".lower()
    code = request.code.strip()

    if any(word in text for word in ["最近", "常犯", "复习", "几次", "统计", "掌握", "错了多少", "薄弱"]):
        return "DATA_QA"
    if code and any(word in text for word in ["错", "报错", "过不了", "不通过", "运行不了", "哪里错", "为什么不对", "为什么错"]):
        return "DEBUG_CODE"
    if any(word in text for word in ["没思路", "不会做", "怎么做", "提示", "给点思路", "先别告诉答案"]):
        return "NEED_HINT"
    if any(word in text for word in ["复盘", "总结", "错题", "下次怎么避免"]):
        return "REVIEW_SUMMARY"
    if any(word in text for word in ["看不懂", "题目什么意思", "什么意思"]):
        return "UNDERSTAND_PROBLEM"
    return "KNOWLEDGE_QA"
