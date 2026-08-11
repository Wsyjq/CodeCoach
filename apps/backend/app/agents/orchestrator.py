from datetime import date, timedelta
from uuid import uuid4

from app.agents.llm_backend import call_agent_llm
from app.agents.router import route_intent
from app.config import settings
from app.schemas.chat import AgentTraceItem, ChatRequest, ChatResponse, Intent, KnowledgeType, NextAction, ReviewCard, SimilarMemory
from app.tools.code_analyzer_tool import analyze_c_code_light
from app.tools.knowledge_tool import search_knowledge_base
from app.tools.memory_tool import find_exact_question_memory, get_memory_by_id, save_review_card, search_learning_memory, similar_memory_from_record
from app.tools.session_tool import load_session_context, write_chat_log
from app.tools.stats_tool import query_learning_stats
from app.tools.trace_tool import write_tool_trace


def handle_chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id.strip() or f"session_{uuid4().hex[:8]}"
    turn_id = f"turn_{uuid4().hex[:12]}"
    session_context = load_session_context(request.user_id, session_id, limit=5)
    is_follow_up = _is_follow_up(request, session_context)
    trace: list[AgentTraceItem] = [
        AgentTraceItem(node="Profile Agent", status="done", detail=_profile_agent_detail(request)),
    ]
    if session_context:
        trace.append(AgentTraceItem(node="Session Memory", status="done", detail=f"{len(session_context)} messages"))
    intent = _route_intent_with_llm(request, session_context)
    trace.append(AgentTraceItem(node="Intent Router", status="done", detail=intent))

    if is_follow_up and intent != "REVIEW_SUMMARY":
        return _finalize_response(
            request,
            session_id,
            turn_id,
            is_follow_up,
            session_context,
            _handle_follow_up(request, intent, trace, session_context, session_id, turn_id),
        )

    if intent == "DATA_QA":
        stats = query_learning_stats(request.user_id, metric=_metric_from_message(request.message), time_range="7d", query=request.message)
        _record_tool_trace(request, session_id, turn_id, "query_learning_stats", {"metric": stats.get("metric"), "query": request.message}, stats)
        trace.append(AgentTraceItem(node="Data Query Tool", status="done", detail=stats.get("metric", "common_errors")))
        fallback_answer = _render_data_answer(stats)
        return _finalize_response(
            request,
            session_id,
            turn_id,
            is_follow_up,
            session_context,
            ChatResponse(
                answer=_llm_or_fallback("DataQA Agent", request, intent, fallback_answer, f"学习数据：{stats}"),
                intent=intent,
                knowledge_type="UNKNOWN",
                knowledge_tags=["学习数据", "问数"],
                agent_trace=trace,
            ),
        )

    if intent == "DEBUG_CODE":
        issues = analyze_c_code_light(request.code)
        _record_tool_trace(request, session_id, turn_id, "analyze_c_code_light", {"code": request.code}, issues)
        issue_type = issues[0]["type"] if issues else "no_rule_hit"
        trace.append(AgentTraceItem(node="Code Analyzer", status="done", detail=_code_analyzer_detail(issues, issue_type)))
        docs = search_knowledge_base(query=f"{request.message} {issue_type}", top_k=2)
        _record_tool_trace(request, session_id, turn_id, "search_knowledge_base", {"query": f"{request.message} {issue_type}", "top_k": 2}, docs)
        trace.append(AgentTraceItem(node="RAG Agent", status="done", detail=_rag_agent_detail(docs)))
        if not issues:
            fallback_answer = _render_debug_answer(issues)
            return _finalize_response(
                request,
                session_id,
                turn_id,
                is_follow_up,
                session_context,
                ChatResponse(
                    answer=_llm_or_fallback(
                        "Debug Agent",
                        request,
                        intent,
                        fallback_answer,
                        f"代码分析结果：{issues}\n知识库片段：{docs['results']}\n未命中内置规则，不生成复盘卡。",
                    ),
                    intent=intent,
                    knowledge_type="UNKNOWN",
                    knowledge_tags=["C语言", "代码分析"],
                    agent_trace=trace,
                ),
            )
        review = _build_review_card(issue_type)
        exact_memory = find_exact_question_memory(request.user_id, request.problem_text, request.code)
        if exact_memory:
            similar = similar_memory_from_record(exact_memory, exact_match=True)
            review_card = _review_card_from_memory(exact_memory)
            _record_tool_trace(
                request,
                session_id,
                turn_id,
                "find_exact_question_memory",
                {"problem_text": request.problem_text, "has_code": bool(request.code.strip())},
                similar.model_dump(),
            )
            trace.append(AgentTraceItem(node="Similarity Agent", status="warning", detail=_exact_memory_trace_detail(exact_memory)))
            trace.append(AgentTraceItem(node="Memory Agent", status="done", detail="exact question reused"))
            fallback_answer = _render_duplicate_question_answer(review_card, exact_memory)
            return _finalize_response(
                request,
                session_id,
                turn_id,
                is_follow_up,
                session_context,
                ChatResponse(
                    answer=_llm_or_fallback(
                        "Debug Agent",
                        request,
                        intent,
                        fallback_answer,
                        f"代码分析结果：{issues}\n已命中完全相同错题：{similar.model_dump()}",
                    ),
                    intent=intent,
                    knowledge_type=review_card.knowledge_type,
                    knowledge_tags=review_card.knowledge_tags,
                    similar_memory=similar,
                    review_card=review_card,
                    agent_trace=trace,
                ),
            )

        similar = search_learning_memory(request.user_id, query=f"{request.message} {request.code}", top_k=1)
        _record_tool_trace(request, session_id, turn_id, "search_learning_memory", {"query": f"{request.message} {request.code}", "top_k": 1}, similar.model_dump())
        if similar.matched:
            trace.append(AgentTraceItem(node="Similarity Agent", status="warning", detail=similar.title))
        knowledge_tags = review.knowledge_tags
        saved_review = save_review_card(
            user_id=request.user_id,
            review_card=review,
            session_id=session_id,
            problem_text=request.problem_text,
            user_code=request.code,
            issue_type=issue_type,
        )
        _record_tool_trace(request, session_id, turn_id, "save_review_card", {"issue_type": issue_type}, saved_review.model_dump())
        trace.append(AgentTraceItem(node="Review Agent", status="done", detail="review card generated"))
        trace.append(AgentTraceItem(node="Memory Agent", status="done", detail=_memory_agent_detail(request, similar)))
        fallback_answer = _render_debug_answer(issues)
        return _finalize_response(
            request,
            session_id,
            turn_id,
            is_follow_up,
            session_context,
            ChatResponse(
                answer=_llm_or_fallback(
                    "Debug Agent",
                    request,
                    intent,
                    fallback_answer,
                    f"代码分析结果：{issues}\n知识库片段：{docs['results']}\n相似记忆：{similar.model_dump()}",
                ),
                intent=intent,
                knowledge_type=saved_review.knowledge_type,
                knowledge_tags=knowledge_tags,
                similar_memory=similar,
                review_card=saved_review,
                agent_trace=trace,
            ),
        )

    if intent == "NEED_HINT":
        docs = search_knowledge_base(query=request.problem_text or request.message, top_k=2)
        _record_tool_trace(request, session_id, turn_id, "search_knowledge_base", {"query": request.problem_text or request.message, "top_k": 2}, docs)
        trace.append(AgentTraceItem(node="Hint Agent", status="done", detail="3-level hint"))
        trace.append(AgentTraceItem(node="RAG Agent", status="done", detail=_rag_agent_detail(docs)))
        fallback_answer = _render_hint_answer(request.problem_text)
        return _finalize_response(
            request,
            session_id,
            turn_id,
            is_follow_up,
            session_context,
            ChatResponse(
                answer=_llm_or_fallback("Hint Agent", request, intent, fallback_answer, f"知识库片段：{docs['results']}"),
                intent=intent,
                knowledge_type="UNDERSTAND",
                knowledge_tags=["解题思路", "分层提示", "C语言"],
                agent_trace=trace,
            ),
        )

    if intent == "UNDERSTAND_PROBLEM":
        trace.append(AgentTraceItem(node="Problem Parser", status="done", detail="input/output/constraint"))
        fallback_answer = _render_problem_answer(request.problem_text)
        return _finalize_response(
            request,
            session_id,
            turn_id,
            is_follow_up,
            session_context,
            ChatResponse(
                answer=_llm_or_fallback("Problem Parser", request, intent, fallback_answer, "请按输入、处理、输出、边界拆解题意。"),
                intent=intent,
                knowledge_type="MIXED",
                knowledge_tags=["题意理解", "输入输出"],
                agent_trace=trace,
            ),
        )

    if intent == "REVIEW_SUMMARY":
        existing_review = _latest_session_review_card(request.user_id, session_context, request.code)
        if existing_review:
            trace.append(AgentTraceItem(node="Review Agent", status="done", detail="session review card reused"))
            trace.append(AgentTraceItem(node="Memory Agent", status="done", detail=existing_review.title))
            fallback_answer = _render_generated_review_answer(existing_review, reused=True)
            return _finalize_response(
                request,
                session_id,
                turn_id,
                is_follow_up,
                session_context,
                ChatResponse(
                    answer=fallback_answer,
                    intent=intent,
                    knowledge_type=existing_review.knowledge_type,
                    knowledge_tags=existing_review.knowledge_tags,
                    review_card=existing_review,
                    agent_trace=trace,
                ),
            )

        review_context = _review_context_from_request_or_session(request, session_context)
        if review_context and review_context["code"].strip():
            issues = analyze_c_code_light(review_context["code"])
            _record_tool_trace(request, session_id, turn_id, "analyze_c_code_light", {"code": review_context["code"]}, issues)
            issue_type = issues[0]["type"] if issues else "no_rule_hit"
            trace.append(AgentTraceItem(node="Code Analyzer", status="done", detail=_code_analyzer_detail(issues, issue_type)))
            review = _build_review_card(issue_type)
            exact_memory = find_exact_question_memory(request.user_id, review_context["problem_text"], review_context["code"])
            if exact_memory:
                similar = similar_memory_from_record(exact_memory, exact_match=True)
                existing_review = _review_card_from_memory(exact_memory)
                _record_tool_trace(
                    request,
                    session_id,
                    turn_id,
                    "find_exact_question_memory",
                    {"problem_text": review_context["problem_text"], "has_code": bool(review_context["code"].strip())},
                    similar.model_dump(),
                )
                trace.append(AgentTraceItem(node="Similarity Agent", status="warning", detail=_exact_memory_trace_detail(exact_memory)))
                trace.append(AgentTraceItem(node="Memory Agent", status="done", detail="exact question reused"))
                fallback_answer = _render_duplicate_question_answer(existing_review, exact_memory)
                return _finalize_response(
                    request,
                    session_id,
                    turn_id,
                    is_follow_up,
                    session_context,
                    ChatResponse(
                        answer=fallback_answer,
                        intent=intent,
                        knowledge_type=existing_review.knowledge_type,
                        knowledge_tags=existing_review.knowledge_tags,
                        similar_memory=similar,
                        review_card=existing_review,
                        agent_trace=trace,
                    ),
                )

            similar = search_learning_memory(request.user_id, query=f"{review_context['message']} {review_context['code']}", top_k=1)
            _record_tool_trace(request, session_id, turn_id, "search_learning_memory", {"query": f"{review_context['message']} {review_context['code']}", "top_k": 1}, similar.model_dump())
            if similar.matched:
                trace.append(AgentTraceItem(node="Similarity Agent", status="warning", detail=similar.title))
            saved_review = save_review_card(
                user_id=request.user_id,
                review_card=review,
                session_id=session_id,
                problem_text=review_context["problem_text"],
                user_code=review_context["code"],
                issue_type=issue_type,
            )
            _record_tool_trace(request, session_id, turn_id, "save_review_card", {"issue_type": issue_type}, saved_review.model_dump())
            trace.append(AgentTraceItem(node="Review Agent", status="done", detail="review card generated from context"))
            trace.append(AgentTraceItem(node="Memory Agent", status="done", detail="saved to memory"))
            fallback_answer = _render_generated_review_answer(saved_review)
            return _finalize_response(
                request,
                session_id,
                turn_id,
                is_follow_up,
                session_context,
                ChatResponse(
                    answer=_llm_or_fallback("Review Agent", request, intent, fallback_answer, f"代码分析结果：{issues}\n复盘卡：{saved_review.model_dump()}"),
                    intent=intent,
                    knowledge_type=saved_review.knowledge_type,
                    knowledge_tags=saved_review.knowledge_tags,
                    similar_memory=similar,
                    review_card=saved_review,
                    agent_trace=trace,
                ),
            )

        stats = query_learning_stats(request.user_id, metric="today_review", time_range="today")
        _record_tool_trace(request, session_id, turn_id, "query_learning_stats", {"metric": "today_review"}, stats)
        trace.append(AgentTraceItem(node="Review Agent", status="done", detail="no code context for review"))
        fallback_answer = (
            "当前会话没有可复盘的代码。请先完成一次代码纠错，再生成复盘。\n\n"
            "最小下一步：回到「代码纠错」服务，粘贴你的 C 代码，系统会自动分析并生成复盘卡。"
        )
        return _finalize_response(
            request,
            session_id,
            turn_id,
            is_follow_up,
            session_context,
            ChatResponse(
                answer=fallback_answer,
                intent=intent,
                knowledge_type="UNKNOWN",
                knowledge_tags=["复盘", "错题本", "学习记忆"],
                agent_trace=trace,
            ),
        )

    docs = search_knowledge_base(query=request.message or request.problem_text, top_k=2)
    _record_tool_trace(request, session_id, turn_id, "search_knowledge_base", {"query": request.message or request.problem_text, "top_k": 2}, docs)
    trace.append(AgentTraceItem(node="RAG Agent", status="done", detail=_rag_agent_detail(docs)))
    fallback_answer = _render_qa_answer(request.message, docs)
    return _finalize_response(
        request,
        session_id,
        turn_id,
        is_follow_up,
        session_context,
        ChatResponse(
            answer=_llm_or_fallback("Tutor Agent", request, intent, fallback_answer, f"知识库片段：{docs['results']}"),
            intent=intent,
            knowledge_type="MEMORIZE" if "scanf" in request.message.lower() else "MIXED",
            knowledge_tags=["C语言", "基础知识"],
            agent_trace=trace,
        ),
    )


def _profile_agent_detail(request: ChatRequest) -> str:
    if not settings.llm_trace_agents:
        return request.user_level
    prompt = (
        "请根据以下信息生成本轮讲解策略。\n\n"
        f"用户水平：{request.user_level}\n"
        f"用户问题：{request.message or '无'}\n"
        f"题目摘要：{request.problem_text or '无'}\n"
        f"是否提供代码：{'是' if request.code.strip() else '否'}\n\n"
        "输出要求：只输出一句中文策略，最多 20 个字；不要解释。"
    )
    return call_agent_llm("Profile Agent", prompt) or request.user_level


def _route_intent_with_llm(request: ChatRequest, session_context: list[dict]) -> Intent:
    normalized_mode = (request.mode or "auto").strip().lower()
    if normalized_mode == "followup":
        return _last_intent_from_context(session_context) or route_intent(request)

    fallback_intent = route_intent(request)
    if normalized_mode != "auto":
        return fallback_intent

    session_hint = _context_summary(session_context) if session_context else "无历史上下文"
    prompt = (
        "请对 mode=auto 的用户请求做意图分类。\n\n"
        "可选标签：KNOWLEDGE_QA、DATA_QA、DEBUG_CODE、NEED_HINT、REVIEW_SUMMARY、UNDERSTAND_PROBLEM。\n\n"
        f"用户问题：{request.message or '无'}\n"
        f"题目：{request.problem_text or '无'}\n"
        f"代码：{request.code or '无'}\n"
        f"会话上下文：{session_hint}\n\n"
        "分类规则：有代码并问错误优先 DEBUG_CODE；问最近常错/薄弱/掌握/复习安排优先 DATA_QA；"
        "明确要复盘或保存错题优先 REVIEW_SUMMARY；没思路或要提示优先 NEED_HINT；"
        "看不懂题目或输入输出优先 UNDERSTAND_PROBLEM；其他知识概念问题为 KNOWLEDGE_QA。\n\n"
        "输出要求：只输出一个标签，不要 JSON、解释或标点。"
    )
    raw_intent = call_agent_llm("Intent Router", prompt)
    valid_intents = {
        "KNOWLEDGE_QA",
        "DATA_QA",
        "DEBUG_CODE",
        "NEED_HINT",
        "REVIEW_SUMMARY",
        "UNDERSTAND_PROBLEM",
    }
    if raw_intent:
        normalized = raw_intent.strip().upper()
        for valid_intent in valid_intents:
            if valid_intent in normalized:
                return valid_intent  # type: ignore[return-value]
    return fallback_intent


def _is_follow_up(request: ChatRequest, session_context: list[dict]) -> bool:
    return (request.mode or "").strip().lower() == "followup"


def _handle_follow_up(
    request: ChatRequest,
    intent: Intent,
    trace: list[AgentTraceItem],
    session_context: list[dict],
    session_id: str,
    turn_id: str,
) -> ChatResponse:
    context_summary = _context_summary(session_context)
    trace.append(AgentTraceItem(node="Follow-up Agent", status="done", detail="session context reused"))
    docs = search_knowledge_base(query=f"{request.message} {context_summary}", top_k=2)
    _record_tool_trace(request, session_id, turn_id, "search_knowledge_base", {"query": f"{request.message} {context_summary}", "top_k": 2}, docs)
    trace.append(AgentTraceItem(node="RAG Agent", status="done", detail=_rag_agent_detail(docs)))
    fallback_answer = _render_followup_answer(request.message, session_context)
    return ChatResponse(
        answer=_llm_or_fallback(
            "Follow-up Agent",
            request,
            intent,
            fallback_answer,
            f"上一轮上下文：{context_summary}\n知识库片段：{docs['results']}",
        ),
        intent=intent,
        knowledge_type=_knowledge_type_from_context(session_context),
        knowledge_tags=_knowledge_tags_from_context(session_context),
        agent_trace=trace,
    )


def _finalize_response(
    request: ChatRequest,
    session_id: str,
    turn_id: str,
    is_follow_up: bool,
    session_context: list[dict],
    response: ChatResponse,
) -> ChatResponse:
    response.session_id = session_id
    response.turn_id = turn_id
    response.is_follow_up = is_follow_up
    response.conversation_title = response.conversation_title or _conversation_title(response, session_context)
    if not response.next_actions:
        response.next_actions = _next_actions(response.intent)
    write_chat_log(request.user_id, session_id, turn_id, request, response)
    return response


def _record_tool_trace(
    request: ChatRequest,
    session_id: str,
    turn_id: str,
    tool_name: str,
    input_data: dict | list | str,
    output_data: dict | list | str,
    status: str = "done",
) -> None:
    write_tool_trace(
        user_id=request.user_id,
        session_id=session_id,
        turn_id=turn_id,
        tool_name=tool_name,
        input_data=input_data,
        output_data=output_data,
        status=status,
        detail=tool_name,
    )


def _last_intent_from_context(session_context: list[dict]) -> Intent | None:
    for item in reversed(session_context):
        intent = item.get("intent")
        if intent in {"KNOWLEDGE_QA", "DATA_QA", "DEBUG_CODE", "NEED_HINT", "REVIEW_SUMMARY", "UNDERSTAND_PROBLEM"}:
            return intent
    return None


def _context_summary(session_context: list[dict]) -> str:
    last_assistant = _last_assistant_context(session_context)
    if not last_assistant:
        return "暂无上一轮上下文"
    title = last_assistant.get("context", {}).get("conversation_title") or "上一轮问题"
    answer = last_assistant.get("answer", "")[:120]
    return f"{title}：{answer}"


def _last_assistant_context(session_context: list[dict]) -> dict | None:
    for item in reversed(session_context):
        if item.get("role") == "assistant":
            return item
    return None


def _knowledge_type_from_context(session_context: list[dict]) -> KnowledgeType:
    last_assistant = _last_assistant_context(session_context)
    knowledge_type = (last_assistant or {}).get("context", {}).get("knowledge_type")
    if knowledge_type in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}:
        return knowledge_type
    return "MIXED"


def _knowledge_tags_from_context(session_context: list[dict]) -> list[str]:
    last_assistant = _last_assistant_context(session_context)
    tags = (last_assistant or {}).get("context", {}).get("knowledge_tags", [])
    if isinstance(tags, list) and tags:
        return tags
    return ["C语言", "继续追问"]


def _conversation_title(response: ChatResponse, session_context: list[dict]) -> str:
    if response.review_card.title:
        return response.review_card.title
    if response.similar_memory.title:
        return response.similar_memory.title
    last_assistant = _last_assistant_context(session_context)
    context_title = (last_assistant or {}).get("context", {}).get("conversation_title")
    if context_title:
        return context_title
    mapping = {
        "KNOWLEDGE_QA": "C 语言知识讲解",
        "DATA_QA": "学习数据分析",
        "DEBUG_CODE": "代码问题分析",
        "NEED_HINT": "分层解题提示",
        "REVIEW_SUMMARY": "错题复盘",
        "UNDERSTAND_PROBLEM": "题目拆解",
    }
    return mapping[response.intent]


def _next_actions(intent: Intent) -> list[NextAction]:
    actions = [
        NextAction(label="再讲简单点", message="再用更简单的话解释一下。", mode="followup"),
        NextAction(label="举个例子", message="能举一个更小的例子吗？", mode="followup"),
        NextAction(label="为什么这样写", message="为什么这里要这样写？", mode="followup"),
    ]
    if intent != "NEED_HINT":
        actions.append(NextAction(label="给我一步提示", message="先别给完整答案，只给下一步提示。", mode="followup"))
    if intent != "REVIEW_SUMMARY":
        actions.append(NextAction(label="生成复盘", message="帮我生成本次错误复盘。", mode="review"))
    return actions


def _memory_agent_detail(request: ChatRequest, similar: SimilarMemory) -> str:
    fallback = similar.title if similar.matched else "similar memory checked"
    if not settings.llm_trace_agents:
        return fallback
    prompt = (
        "请生成相似错题提醒摘要。\n\n"
        f"用户问题：{request.message or '无'}\n"
        f"代码摘要：{request.code[:300] or '无'}\n"
        f"是否命中历史记忆：{similar.matched}\n"
        f"历史记忆标题：{similar.title or '无'}\n"
        f"历史错因：{similar.mistake_summary or '无'}\n"
        f"复习建议：{similar.review_tip or '无'}\n\n"
        "输出要求：只输出一句中文提醒，最多 20 个字；未命中时输出“暂无明显相似错题”。"
    )
    return call_agent_llm("Memory Agent", prompt) or fallback


def _exact_memory_trace_detail(memory: dict) -> str:
    seen_at = _memory_first_seen(memory)
    return f"{memory.get('title', '历史错题')} · {seen_at} 已问过"


def _code_analyzer_detail(issues: list[dict], fallback_issue_type: str) -> str:
    if not settings.llm_trace_agents:
        return fallback_issue_type
    prompt = (
        "请根据本地规则分析结果总结首要代码问题。\n\n"
        f"规则命中结果：{issues}\n"
        f"兜底错误类型：{fallback_issue_type}\n\n"
        "输出要求：只输出一句中文摘要，最多 20 个字；不要新增工具未命中的错误。"
    )
    return call_agent_llm("Code Analyzer", prompt) or fallback_issue_type


def _rag_agent_detail(docs: dict) -> str:
    results = docs.get("results", [])
    fallback = f"{len(results)} docs"
    if not settings.llm_trace_agents:
        return fallback
    prompt = (
        "请判断知识库片段能支撑的教学重点。\n\n"
        f"检索结果数量：{len(results)}\n"
        f"检索片段：{results}\n\n"
        "输出要求：只输出一句中文摘要，最多 20 个字；片段为空或不相关时输出“知识命中不足”。"
    )
    return call_agent_llm("RAG Agent", prompt) or fallback


def _latest_session_review_card(user_id: str, session_context: list[dict], request_code: str = "") -> ReviewCard | None:
    normalized_code = request_code.strip()
    for item in reversed(session_context):
        review_card_id = item.get("context", {}).get("review_card_id")
        if not review_card_id:
            continue
        context_code = (item.get("code") or "").strip()
        if normalized_code and context_code != normalized_code:
            continue
        memory = get_memory_by_id(user_id, review_card_id)
        if memory:
            return _review_card_from_memory(memory)
    return None


def _review_context_from_request_or_session(request: ChatRequest, session_context: list[dict]) -> dict | None:
    if request.code.strip():
        return {
            "message": request.message,
            "problem_text": request.problem_text,
            "code": request.code,
        }
    for item in reversed(session_context):
        if item.get("role") == "user" and (item.get("code") or "").strip():
            return {
                "message": item.get("message") or request.message,
                "problem_text": item.get("problem_text") or request.problem_text,
                "code": item.get("code") or "",
            }
    for item in reversed(session_context):
        if (item.get("code") or "").strip():
            return {
                "message": item.get("message") or request.message,
                "problem_text": item.get("problem_text") or request.problem_text,
                "code": item.get("code") or "",
            }
    return None


def _review_card_from_memory(memory: dict) -> ReviewCard:
    knowledge_type = memory.get("knowledge_type")
    if knowledge_type not in {"MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"}:
        knowledge_type = "UNKNOWN"
    return ReviewCard(
        id=str(memory.get("id") or ""),
        title=str(memory.get("title") or ""),
        error_type=str(memory.get("error_type") or ""),
        knowledge_type=knowledge_type,
        knowledge_tags=_string_list(memory.get("knowledge_tags")),
        mistake_summary=str(memory.get("mistake_summary") or ""),
        review_tip=str(memory.get("review_tip") or ""),
        remember_points=_string_list(memory.get("remember_points")),
        understand_points=_string_list(memory.get("understand_points")),
        common_mistakes=_string_list(memory.get("common_mistakes")),
        next_review_at=str(memory.get("next_review_at") or ""),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _llm_or_fallback(agent_name: str, request: ChatRequest, intent: str, fallback_answer: str, context: str) -> str:
    prompt = (
        f"你正在作为 {agent_name} 生成给学生看的回答。\n\n"
        "任务输入：\n"
        f"用户水平：{request.user_level}\n"
        f"意图标签：{intent}\n"
        f"用户问题：{request.message or '无'}\n"
        f"题目：{request.problem_text or '无'}\n"
        f"代码：{request.code or '无'}\n"
        f"工具和会话上下文：{context}\n\n"
        "本地降级回答参考：\n"
        f"{fallback_answer}\n\n"
        "输出要求：\n"
        "1. 面向 C 语言初学者，150 到 300 字。\n"
        "2. 先给一句话结论，再解释原因，再给最小下一步。\n"
        "3. 不使用 emoji，不输出复杂 Markdown，不直接给完整题解代码。\n"
        "4. 不要编造工具结果、学习数据或历史错题；不要提到“本地降级回答”。"
    )
    return call_agent_llm(agent_name, prompt) or fallback_answer


def _build_review_card(issue_type: str) -> ReviewCard:
    mapping = {
        "scanf_missing_address": ("scanf 输入错误", "C语法错误"),
        "assignment_in_condition": ("条件判断赋值误用", "C语法错误"),
        "array_boundary_risk": ("数组循环边界风险", "循环边界错误"),
        "binary_search_boundary_risk": ("二分查找边界不收缩", "算法边界错误"),
        "uninitialized_variable_risk": ("变量未初始化风险", "C语法错误"),
        "scanf_argument_count_mismatch": ("scanf 参数数量不匹配", "C语法错误"),
        "loop_update_missing": ("循环变量未更新", "循环边界错误"),
        "infinite_loop_risk": ("死循环风险", "循环边界错误"),
        "recursive_base_case_missing": ("递归缺少终止条件", "算法边界错误"),
        "string_missing_terminator_risk": ("字符串结束符风险", "C语法错误"),
    }
    title, error_type = mapping.get(issue_type, ("代码问题待复盘", "代码分析未命中"))
    details = _review_details_from_issue(issue_type)
    return ReviewCard(
        id=f"review_{issue_type}",
        title=title,
        error_type=error_type,
        knowledge_type=details["knowledge_type"],
        knowledge_tags=_knowledge_tags_from_issue(issue_type),
        mistake_summary=details["mistake_summary"],
        review_tip=details["review_tip"],
        remember_points=details["remember_points"],
        understand_points=details["understand_points"],
        common_mistakes=details["common_mistakes"],
        next_review_at=(date.today() + timedelta(days=1)).isoformat(),
    )


def _knowledge_tags_from_issue(issue_type: str) -> list[str]:
    mapping = {
        "scanf_missing_address": ["C语言", "scanf", "输入", "取地址"],
        "assignment_in_condition": ["C语言", "条件判断", "赋值", "比较"],
        "array_boundary_risk": ["C语言", "数组", "循环边界", "越界"],
        "binary_search_boundary_risk": ["算法", "二分查找", "边界", "循环"],
        "uninitialized_variable_risk": ["C语言", "变量", "初始化"],
        "scanf_argument_count_mismatch": ["C语言", "scanf", "格式符", "输入"],
        "loop_update_missing": ["C语言", "循环", "更新表达式"],
        "infinite_loop_risk": ["C语言", "循环", "死循环"],
        "recursive_base_case_missing": ["算法", "递归", "终止条件"],
        "string_missing_terminator_risk": ["C语言", "字符串", "结束符"],
    }
    return mapping.get(issue_type, ["C语言", "代码分析"])


def _review_details_from_issue(issue_type: str) -> dict:
    mapping = {
        "scanf_missing_address": {
            "knowledge_type": "MEMORIZE",
            "mistake_summary": "用户在 scanf 中忘记给普通变量加 &。",
            "review_tip": "读取普通变量时通常要传变量地址。",
            "remember_points": ["scanf 读取普通变量时通常要加 &"],
            "understand_points": ["scanf 需要变量地址，才能把输入值写回变量"],
            "common_mistakes": ["把 scanf(\"%d\", &n) 写成 scanf(\"%d\", n)", "混淆普通变量和数组名是否需要 &"],
        },
        "assignment_in_condition": {
            "knowledge_type": "MEMORIZE",
            "mistake_summary": "用户在条件判断中疑似把赋值符号 = 当成比较符号 ==。",
            "review_tip": "看到 if 条件里的单个 = 时，先确认是否应该写成 ==。",
            "remember_points": ["= 是赋值，== 才是比较是否相等"],
            "understand_points": ["if 条件会使用赋值表达式的结果继续判断真假"],
            "common_mistakes": ["if (x = 1) 误写成判断", "把赋值表达式放进条件里但没有意识到副作用"],
        },
        "array_boundary_risk": {
            "knowledge_type": "UNDERSTAND",
            "mistake_summary": "用户循环访问数组时存在 <= n 导致越界的风险。",
            "review_tip": "数组长度为 n 时，重点检查最后一个合法下标是否是 n - 1。",
            "remember_points": ["长度为 n 的数组最后一个合法下标是 n - 1"],
            "understand_points": ["循环到 i == n 时访问 a[n] 已经越过数组末尾"],
            "common_mistakes": ["for 循环条件把 < n 写成 <= n", "数组容量和输入规模 n 没有对应检查"],
        },
        "binary_search_boundary_risk": {
            "knowledge_type": "UNDERSTAND",
            "mistake_summary": "用户在二分查找中使用 left = mid，可能导致区间不收缩。",
            "review_tip": "每次更新边界后都要确认搜索区间严格变小。",
            "remember_points": ["二分查找每轮必须缩小区间"],
            "understand_points": ["当 mid 等于 left 时，left = mid 会让下一轮得到同一个 mid"],
            "common_mistakes": ["left = mid 导致死循环", "right = mid 时没有配套循环条件"],
        },
        "uninitialized_variable_risk": {
            "knowledge_type": "MEMORIZE",
            "mistake_summary": "用户可能在局部变量赋值前就输出或使用它。",
            "review_tip": "检查变量第一次使用前是否已经输入、赋值或计算。",
            "remember_points": ["C 语言局部变量声明后不会自动初始化成 0"],
            "understand_points": ["未初始化变量里的值来自当前栈内存，结果不可预测"],
            "common_mistakes": ["声明 int n 后直接 printf", "只在部分分支里给变量赋值"],
        },
        "scanf_argument_count_mismatch": {
            "knowledge_type": "MEMORIZE",
            "mistake_summary": "用户的 scanf 格式符数量和后面的输入参数数量不一致。",
            "review_tip": "每写一个有效格式符，就检查后面是否有一个对应变量地址。",
            "remember_points": ["scanf 的格式符和参数要一一对应"],
            "understand_points": ["参数少了会导致输入无法写入目标变量，参数多了说明格式和数据不匹配"],
            "common_mistakes": ["scanf(\"%d%d\", &a) 少传一个参数", "格式字符串改了但后面的变量没有同步修改"],
        },
        "loop_update_missing": {
            "knowledge_type": "UNDERSTAND",
            "mistake_summary": "用户的 for 循环缺少更新表达式，循环变量可能不会变化。",
            "review_tip": "看到 for 循环时，依次检查初始化、条件和更新三段是否完整。",
            "remember_points": ["for 循环第三段通常负责推进循环变量"],
            "understand_points": ["如果循环变量不变化，循环条件可能一直成立"],
            "common_mistakes": ["for (i = 0; i < n;) 忘记 i++", "把更新写进了错误的分支里"],
        },
        "infinite_loop_risk": {
            "knowledge_type": "UNDERSTAND",
            "mistake_summary": "用户写了恒真循环，但没有明显退出条件。",
            "review_tip": "使用 while(1) 或 for(;;) 时，先确认循环内部一定能执行到 break 或 return。",
            "remember_points": ["恒真循环必须配套明确退出条件"],
            "understand_points": ["没有退出条件时，程序会一直占用运行流程，无法到达后续代码"],
            "common_mistakes": ["while(1) 内没有 break", "break 写在永远不会进入的条件分支里"],
        },
        "recursive_base_case_missing": {
            "knowledge_type": "UNDERSTAND",
            "mistake_summary": "用户的递归函数疑似缺少终止条件。",
            "review_tip": "写递归前先写 base case，再写递归调用。",
            "remember_points": ["递归必须有终止条件"],
            "understand_points": ["没有 base case 时，函数会不断调用自己直到栈溢出"],
            "common_mistakes": ["只写 f(n - 1) 没写 n == 0", "终止条件写了但递归参数没有向终止条件靠近"],
        },
        "string_missing_terminator_risk": {
            "knowledge_type": "MEMORIZE",
            "mistake_summary": "用户把字符数组当字符串输出，但没有看到字符串结束符。",
            "review_tip": "手动填充 char 数组后，按字符串输出前要补 \\0。",
            "remember_points": ["C 字符串需要以 \\0 结尾"],
            "understand_points": ["printf(\"%s\") 会一直读到 \\0 才停止"],
            "common_mistakes": ["char s[3] 只填 a、b、c 就按 %s 输出", "数组长度没有给结束符预留位置"],
        },
    }
    return mapping.get(
        issue_type,
        {
            "knowledge_type": "UNKNOWN",
            "mistake_summary": "本次代码问题需要补充复盘。",
            "review_tip": "下次先补充报错信息和样例输入输出。",
            "remember_points": ["先记录触发错误的输入和现象"],
            "understand_points": ["结合题目、代码和运行结果一起定位问题"],
            "common_mistakes": ["只贴代码但没有说明输入输出", "忽略编译器或评测系统的报错信息"],
        },
    )


def _metric_from_message(message: str) -> str:
    if "复习" in message or "今天" in message:
        return "today_review"
    if "薄弱" in message or "没掌握" in message or "弱" in message:
        return "weak_concepts"
    if "类似" in message or "上次" in message:
        return "last_similar_mistake"
    if "语法" in message and "算法" in message:
        return "error_type_ratio"
    if "二分" in message or "scanf" in message or "数组" in message or "几次" in message:
        return "concept_attempt_count"
    return "common_errors"


def _render_data_answer(stats: dict) -> str:
    metric = stats.get("metric")
    if metric == "today_review":
        items = stats.get("due_reviews", [])
        if not items:
            return "今天暂无到期复习。建议先完成一次代码纠错，生成复盘卡片。"
        names = "、".join(item["title"] for item in items)
        return f"今天建议复习：{names}。这些内容来自你的错题复盘记录。"
    if metric == "weak_concepts":
        items = stats.get("weak_concepts", [])
        if not items:
            return "目前还没有足够错题数据判断薄弱知识。先完成一次代码纠错，系统会生成学习画像。"
        rendered = "；".join(f"{item['concept']} {item['wrong_count']} 次" for item in items[:3])
        return f"你当前最需要关注的薄弱知识是：{rendered}。建议先复习出现次数最多的知识点。"
    if metric == "last_similar_mistake":
        similar = stats.get("similar_memory", {})
        if similar.get("matched"):
            return f"上次类似错误是：{similar['title']}。{similar.get('mistake_summary', '')} 下次提醒：{similar.get('review_tip', '')}"
        return "暂时没有找到类似错题。你可以先提交代码纠错，系统会把这次错误保存成复盘卡。"
    if metric == "error_type_ratio":
        return (
            f"最近记录中，语法类错误 {stats.get('syntax_errors', 0)} 次，"
            f"算法类错误 {stats.get('algorithm_errors', 0)} 次，边界类错误 {stats.get('boundary_errors', 0)} 次。"
            "先处理数量最多的一类。"
        )
    if metric == "concept_attempt_count":
        return f"你在 {stats.get('concept', '这个知识点')} 相关问题上有 {stats.get('count', 0)} 次错误记录。建议从最近错题开始复盘。"
    top = stats.get("top_errors", [])
    rendered = "；".join(f"{item['error_type']} {item['count']} 次" for item in top)
    return f"最近你最常见的错误是：{rendered}。建议优先复习数组下标、scanf 输入格式和循环边界。"


def _render_followup_answer(message: str, session_context: list[dict]) -> str:
    context_summary = _context_summary(session_context)
    if "例" in message:
        return (
            f"我们接着刚才的内容看：{context_summary}\n\n"
            "换成一个更小的例子：如果 scanf 要把键盘输入的 3 放进变量 n，它必须知道 n 在内存里的位置，"
            "所以普通变量要传 &n。你可以先把 & 理解成“把变量地址交给 scanf”。"
        )
    if "简单" in message or "不懂" in message:
        return (
            f"接着刚才的问题：{context_summary}\n\n"
            "先不用想太深，可以记成一句话：想让函数帮你改某个普通变量，就要把这个变量的位置给它。"
            "scanf 要写入输入值，所以普通变量前通常要加 &。"
        )
    if "提示" in message:
        return (
            f"基于上一轮：{context_summary}\n\n"
            "下一步提示：先只检查一个最关键位置，找到输入、循环条件或边界更新里最像固定规则的那一行。"
        )
    return (
        f"我们沿着上一轮继续：{context_summary}\n\n"
        "这次先抓住核心原因，再看写法规则。你可以把当前问题拆成两步：第一步判断它属于固定语法还是算法边界，"
        "第二步用一个最小例子验证为什么要这样写。"
    )


def _render_debug_answer(issues: list[dict]) -> str:
    if not issues:
        return (
            "暂时没有命中内置代码规则，所以这次不会自动生成复盘卡。\n\n"
            "请补充四类信息中的至少两类：编译/运行报错、样例输入、期望输出、实际输出。\n\n"
            "最小下一步：先贴一组让程序出错的输入和对应的实际输出，我再继续帮你定位。"
        )
    first = issues[0]
    if first["type"] == "scanf_missing_address":
        return (
            "问题可能出在 `scanf` 这一行。\n\n"
            "这是 C 语言输入的固定规则，属于记忆型知识。`scanf` 需要变量地址，普通 `int` 变量前通常要加 `&`。\n\n"
            "最小提示：检查 `scanf(\"%d\", n);` 中的 `n` 前面是否缺少 `&`。"
        )
    if first["type"] == "assignment_in_condition":
        return "条件判断里疑似把 `=` 当成了 `==`。`=` 是赋值，`==` 才是比较是否相等。"
    if first["type"] == "array_boundary_risk":
        return (
            "这里有数组越界风险。\n\n"
            "如果数组长度是 `n`，最后一个合法下标通常是 `n - 1`。循环条件写成 `<= n` 时，"
            "很容易访问到 `a[n]`。\n\n"
            "最小提示：检查循环终止条件是否应该是 `< n`。"
        )
    if first["type"] == "binary_search_boundary_risk":
        return "这里有二分边界风险。`left = mid` 可能导致区间没有缩小，建议思考是否应该跳过 `mid`。"
    if first["type"] == "uninitialized_variable_risk":
        return (
            "这里疑似有变量未初始化就使用的问题。\n\n"
            "C 语言里的局部变量声明后不会自动变成你想要的值，如果没有先赋值、输入或计算，"
            "直接输出或参与运算会得到不确定结果。\n\n"
            "最小提示：找到这个变量第一次被使用的位置，再向上检查它之前有没有被赋值。"
        )
    if first["type"] == "scanf_argument_count_mismatch":
        return "这里的 scanf 格式符和后面的参数数量不一致。最小提示：数一数格式字符串里有几个 %，再数后面有几个变量地址。"
    if first["type"] == "loop_update_missing":
        return "这个 for 循环缺少更新表达式，循环变量可能不会推进。最小提示：检查第三段是否需要写 i++ 或类似更新。"
    if first["type"] == "infinite_loop_risk":
        return "这里有死循环风险。恒真循环可以使用，但必须确认循环体里有明确的 break 或 return。"
    if first["type"] == "recursive_base_case_missing":
        return "这个递归函数疑似缺少终止条件。最小提示：先写 n == 0 或 n == 1 这类 base case，再写递归调用。"
    if first["type"] == "string_missing_terminator_risk":
        return "字符数组按字符串输出时需要以 `\\0` 结尾。最小提示：检查是否给结束符预留并赋值。"
    return first["message"]


def _render_qa_answer(message: str, docs: dict) -> str:
    if "scanf" in message.lower():
        return (
            "`scanf` 加 `&` 属于 C 语言固定规则，可以先记住。\n\n"
            "`scanf` 需要拿到变量的地址，才能把输入值写进变量里。比如读取整数时常写成：`scanf(\"%d\", &n);`。\n\n"
            "容易误解的地方：普通变量通常要加 `&`，但数组名本身常常已经可以表示地址。"
        )
    if docs.get("results"):
        title = docs["results"][0]["title"]
        return f"我先从知识库中找到相关知识：{title}。这类问题建议先看输入输出和边界条件，再拆成可实现的步骤。"
    return "我会先帮你拆题意，再根据你的当前水平给出分层提示。"


def _render_hint_answer(problem_text: str) -> str:
    subject = "这道题" if problem_text else "当前问题"
    return (
        f"先不给完整答案，我们按三层提示拆 {subject}：\n\n"
        "1. 先确认输入里有哪些变量，以及最终要输出什么。\n"
        "2. 把样例手算一遍，找出循环或判断条件。\n"
        "3. 写代码前先确定边界：循环从哪里开始，到哪里结束，是否会访问越界。"
    )


def _render_problem_answer(problem_text: str) -> str:
    if not problem_text:
        return "你可以把题目原文贴进来，我会按输入、输出、限制条件和解题步骤帮你拆。"
    return (
        "我先把题目拆成四块：\n\n"
        f"题目原文：{problem_text}\n\n"
        "输入：先找到需要读取的变量。\n"
        "处理：判断是直接输出、循环累计，还是需要数组/算法。\n"
        "输出：确认格式，尤其是空格和换行。\n"
        "边界：新手最容易漏掉 0、1、最大值这些情况。"
    )


def _render_generated_review_answer(review_card: ReviewCard, reused: bool = False) -> str:
    action = "已经找到刚才生成并保存到错题本的复盘卡，不会重复新增" if reused else "已经根据本轮上下文生成复盘卡"
    remember = "；".join(review_card.remember_points) or review_card.review_tip or "先记录本次最小错误规则"
    understand = "；".join(review_card.understand_points) or "复述为什么会错，以及下次怎么检查"
    return (
        f"{action}：{review_card.title or '本次错题复盘'}。\n\n"
        f"错因：{review_card.mistake_summary or '本次问题需要结合代码和题目继续复述。'}\n\n"
        f"需要记住：{remember}\n\n"
        f"需要理解：{understand}\n\n"
        f"下次检查：{review_card.review_tip or '先定位最小出错行，再检查固定规则和边界条件。'}"
    )


def _render_duplicate_question_answer(review_card: ReviewCard, memory: dict) -> str:
    seen_at = _memory_first_seen(memory)
    remember = "；".join(review_card.remember_points) or review_card.review_tip or "先记录本次最小错误规则"
    understand = "；".join(review_card.understand_points) or "复述为什么会错，以及下次怎么检查"
    return (
        f"这道题你在 {seen_at} 已经问过一模一样的了，我不会把它重复加入「我的错题」。\n\n"
        f"历史错题：{review_card.title or '本次错题复盘'}。\n\n"
        f"当时错因：{review_card.mistake_summary or '这条错题还在整理中。'}\n\n"
        f"需要记住：{remember}\n\n"
        f"需要理解：{understand}\n\n"
        f"这次请重点检查：{review_card.review_tip or '先定位最小出错行，再检查固定规则和边界条件。'}"
    )


def _memory_first_seen(memory: dict) -> str:
    return str(memory.get("first_seen_at") or memory.get("created_at") or memory.get("last_seen_at") or "之前")


def _render_review_answer(stats: dict) -> str:
    items = stats.get("due_reviews", [])
    if not items:
        return "今天没有到期复盘。建议完成一道新题后生成一张错题复盘卡。"
    rendered = "\n".join(f"- {item['title']}：{item['error_type']}" for item in items)
    return f"今天建议复盘这些内容：\n\n{rendered}\n\n复盘时不要只看答案，重点回答：我当时为什么会错？下次遇到什么信号要警惕？"
