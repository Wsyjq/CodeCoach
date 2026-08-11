from collections import Counter
from datetime import date

from app.tools.memory_tool import list_demo_memories, search_learning_memory


def query_learning_stats(
    user_id: str,
    metric: str,
    time_range: str = "7d",
    limit: int | None = None,
    target_date: str | None = None,
    status: str | None = None,
    query: str = "",
) -> dict:
    memories = list_demo_memories(user_id)
    review_cutoff = target_date or date.today().isoformat()
    if metric == "today_review":
        due_reviews = _due_reviews(memories, review_cutoff, status=status, limit=limit)
        return {
            "metric": metric,
            "time_range": time_range,
            "target_date": review_cutoff,
            "due_count": len(due_reviews),
            "due_reviews": due_reviews,
            "recommended_actions": _review_actions(due_reviews),
        }
    if metric == "weak_concepts":
        weak_concepts = _weak_concepts(memories)
        return {
            "metric": metric,
            "time_range": time_range,
            "weak_concepts": weak_concepts,
            "weak_tags": [item["concept"] for item in weak_concepts[:3]],
            "recommended_actions": [f"优先复习 {item['concept']}，它在错题中出现 {item['wrong_count']} 次。" for item in weak_concepts[:2]],
        }
    if metric == "error_type_ratio":
        syntax_errors = sum(1 for item in memories if "语法" in item["error_type"])
        algorithm_errors = sum(1 for item in memories if "算法" in item["error_type"])
        boundary_errors = sum(1 for item in memories if "边界" in item["error_type"] or "边界" in item["title"])
        total = len(memories) or 1
        return {
            "metric": metric,
            "time_range": time_range,
            "total_records": len(memories),
            "syntax_errors": syntax_errors,
            "algorithm_errors": algorithm_errors,
            "boundary_errors": boundary_errors,
            "syntax_ratio": round(syntax_errors / total, 2),
            "algorithm_ratio": round(algorithm_errors / total, 2),
            "boundary_ratio": round(boundary_errors / total, 2),
            "recommended_actions": _ratio_actions(syntax_errors, algorithm_errors, boundary_errors),
        }
    if metric == "concept_attempt_count":
        concept = _extract_concept(query) or "二分查找"
        count = sum(1 for item in memories if concept in item["knowledge_tags"] or concept in item["title"])
        recent_reviews = [item for item in _recent_reviews(memories, limit=5) if concept in item["knowledge_tags"] or concept in item["title"]]
        return {
            "metric": metric,
            "time_range": time_range,
            "concept": concept,
            "count": count,
            "recent_reviews": recent_reviews,
            "recommended_actions": [f"{concept} 相关错题共 {count} 条，建议先复盘最近一条。"] if count else [f"暂时没有 {concept} 相关错题。"],
        }
    if metric == "last_similar_mistake":
        similar = search_learning_memory(user_id, query=query, top_k=1)
        return {
            "metric": metric,
            "time_range": time_range,
            "similar_memory": similar.model_dump(),
            "recommended_actions": [similar.review_tip] if similar.matched and similar.review_tip else ["暂时没有命中类似错题，可以先完成一次代码纠错生成复盘。"],
        }
    error_counts = Counter(item["error_type"] for item in memories)
    tag_counts = Counter(tag for item in memories for tag in item["knowledge_tags"])
    weak_tags = [key for key, _ in tag_counts.most_common(3)]
    due_reviews = _due_reviews(memories, review_cutoff, status=status, limit=limit)
    return {
        "metric": "common_errors",
        "time_range": time_range,
        "total_records": len(memories),
        "top_errors": [
            {"error_type": key, "count": value}
            for key, value in error_counts.most_common()
        ],
        "weak_tags": weak_tags,
        "weak_concepts": _weak_concepts(memories),
        "review_due_count": len(due_reviews),
        "due_reviews": due_reviews[:3],
        "recent_reviews": _recent_reviews(memories, limit=3),
        "mastery_avg": _mastery_avg(memories),
        "recommended_actions": _summary_actions(weak_tags, due_reviews),
    }


def _due_reviews(memories: list[dict], review_cutoff: str, status: str | None = None, limit: int | None = None) -> list[dict]:
    due_items = [
        item
        for item in memories
        if item["next_review_at"] <= review_cutoff
        and (item.get("mastery_status") == status if status else item.get("mastery_status") != "mastered")
    ]
    due_items.sort(key=lambda item: (item["next_review_at"], item.get("mastery", 1.0)))
    if limit is not None:
        due_items = due_items[: max(limit, 0)]
    return [_review_summary(item) for item in due_items]


def _review_summary(item: dict) -> dict:
    return {
        "id": item["id"],
        "title": item["title"],
        "error_type": item["error_type"],
        "knowledge_type": item["knowledge_type"],
        "knowledge_tags": item["knowledge_tags"],
        "mistake_summary": item["mistake_summary"],
        "review_tip": item["review_tip"],
        "next_review_at": item["next_review_at"],
        "mastery": item["mastery"],
        "mastery_status": item["mastery_status"],
    }


def _weak_concepts(memories: list[dict]) -> list[dict]:
    tag_counts = Counter(tag for item in memories for tag in item["knowledge_tags"])
    concept_scores = []
    for concept, wrong_count in tag_counts.most_common():
        related = [item for item in memories if concept in item["knowledge_tags"]]
        concept_scores.append(
            {
                "concept": concept,
                "wrong_count": wrong_count,
                "mastery_avg": _mastery_avg(related),
                "last_seen_at": max((item["last_seen_at"] for item in related), default=""),
            }
        )
    concept_scores.sort(key=lambda item: (-item["wrong_count"], item["mastery_avg"]))
    return concept_scores[:5]


def _recent_reviews(memories: list[dict], limit: int = 3) -> list[dict]:
    recent = sorted(memories, key=lambda item: item.get("last_seen_at", ""), reverse=True)[:limit]
    return [_review_summary(item) for item in recent]


def _mastery_avg(memories: list[dict]) -> float:
    return round(sum(item["mastery"] for item in memories) / len(memories), 2) if memories else 0.0


def _extract_concept(query: str) -> str:
    for concept in ["二分查找", "scanf", "数组", "循环边界", "变量", "初始化", "条件判断"]:
        if concept in query:
            return concept
    return ""


def _summary_actions(weak_tags: list[str], due_reviews: list[dict]) -> list[str]:
    actions = []
    if weak_tags:
        actions.append(f"优先复习 {weak_tags[0]}。")
    if len(weak_tags) > 1:
        actions.append(f"做题时重点检查 {weak_tags[1]} 相关规则。")
    if due_reviews:
        actions.append(f"今天有 {len(due_reviews)} 张复盘卡到期，先看 {due_reviews[0]['title']}。")
    return actions or ["先完成一次代码纠错，系统会自动生成错题复盘。"]


def _review_actions(due_reviews: list[dict]) -> list[str]:
    if not due_reviews:
        return ["今天暂无到期复习，可以先做一道新题。"]
    return [f"先复习 {due_reviews[0]['title']}。", "复习时先说出错因，再看记忆点和理解点。"]


def _ratio_actions(syntax_errors: int, algorithm_errors: int, boundary_errors: int) -> list[str]:
    if syntax_errors >= algorithm_errors and syntax_errors >= boundary_errors:
        return ["语法类错误最多，优先巩固 C 语言固定规则。"]
    if boundary_errors >= algorithm_errors:
        return ["边界类错误较多，做题时先手算最小和最大样例。"]
    return ["算法类错误较多，先复盘题意拆解和循环不变量。"]
