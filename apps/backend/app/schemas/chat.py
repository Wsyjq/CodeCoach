from typing import Literal

from pydantic import BaseModel, Field


Intent = Literal[
    "KNOWLEDGE_QA",
    "DATA_QA",
    "DEBUG_CODE",
    "NEED_HINT",
    "REVIEW_SUMMARY",
    "UNDERSTAND_PROBLEM",
]

KnowledgeType = Literal["MEMORIZE", "UNDERSTAND", "MIXED", "UNKNOWN"]

ServiceMode = Literal["auto", "knowledge", "problem", "hint", "debug", "data", "review", "followup"]


class ChatRequest(BaseModel):
    user_id: str = "demo_user"
    user_level: Literal["beginner", "basic", "advanced"] = "beginner"
    message: str = ""
    problem_text: str = ""
    code: str = ""
    mode: ServiceMode | str = "auto"
    session_id: str = "session_001"


class SimilarMemory(BaseModel):
    matched: bool = False
    id: str = ""
    title: str = ""
    mistake_summary: str = ""
    review_tip: str = ""
    score: float = 0.0
    first_seen_at: str = ""
    last_seen_at: str = ""
    occurrence_count: int = 0
    exact_match: bool = False


class ReviewCard(BaseModel):
    id: str = ""
    title: str = ""
    error_type: str = ""
    knowledge_type: KnowledgeType = "UNKNOWN"
    knowledge_tags: list[str] = Field(default_factory=list)
    mistake_summary: str = ""
    review_tip: str = ""
    remember_points: list[str] = Field(default_factory=list)
    understand_points: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    next_review_at: str = ""


class NextAction(BaseModel):
    label: str
    message: str
    mode: ServiceMode = "followup"


class AgentTraceItem(BaseModel):
    node: str
    status: Literal["waiting", "running", "done", "warning", "error"] = "done"
    detail: str = ""


class ChatResponse(BaseModel):
    session_id: str = ""
    turn_id: str = ""
    is_follow_up: bool = False
    conversation_title: str = ""
    answer: str
    intent: Intent
    knowledge_type: KnowledgeType = "UNKNOWN"
    knowledge_tags: list[str] = Field(default_factory=list)
    similar_memory: SimilarMemory = Field(default_factory=SimilarMemory)
    review_card: ReviewCard = Field(default_factory=ReviewCard)
    next_actions: list[NextAction] = Field(default_factory=list)
    agent_trace: list[AgentTraceItem] = Field(default_factory=list)
