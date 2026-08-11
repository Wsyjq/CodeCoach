import json
import logging
from pathlib import Path

from app.vectorstore.chroma_client import COLLECTION_KNOWLEDGE, search_similar

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_SEED_DIR = PROJECT_ROOT / "data" / "knowledge_seed"
KNOWLEDGE_SEED_FILES = [
    "c_basics.jsonl",
    "c_mistakes.jsonl",
    "problem_patterns.jsonl",
    "algorithms_c.jsonl",
]

DEMO_KNOWLEDGE = [
    {
        "id": "c_scanf_001",
        "title": "scanf 读取普通变量时需要传地址",
        "content": "scanf 需要变量地址，普通变量前通常需要加 &。",
        "source": "CodeCoach contributors",
        "license": "MIT",
        "tags": ["C语言", "scanf", "输入"],
    },
    {
        "id": "c_array_bounds_001",
        "title": "C 语言数组下标与越界",
        "content": "长度为 n 的数组，合法下标是 0 到 n-1。",
        "source": "CodeCoach contributors",
        "license": "MIT",
        "tags": ["C语言", "数组", "越界"],
    },
    {
        "id": "algo_binary_search_001",
        "title": "二分查找边界更新",
        "content": "二分查找每轮必须让搜索区间缩小，否则可能死循环。",
        "source": "CodeCoach contributors",
        "license": "MIT",
        "tags": ["二分查找", "边界", "数组"],
    },
]


_MIN_CHROMA_SCORE = 0.08


def search_knowledge_base(query: str, top_k: int = 3, tags: list[str] | None = None) -> dict:
    where = _build_where_from_tags(tags)
    chroma_top_k = max(top_k, min(10, top_k * 4))
    chroma_results = search_similar(COLLECTION_KNOWLEDGE, query, chroma_top_k, where=where)
    if chroma_results and chroma_results[0].get("score", 0) >= _MIN_CHROMA_SCORE:
        query_text = query.lower()
        reranked = sorted(
            chroma_results,
            key=lambda result: (
                _score_knowledge_item(_chroma_to_result(result), query_text, tags),
                result.get("score", 0),
            ),
            reverse=True,
        )
        return {"results": [_chroma_to_result(r) for r in reranked[:top_k]]}

    items = load_knowledge_cards() or DEMO_KNOWLEDGE
    query_text = query.lower()
    scored: list[tuple[int, dict]] = []
    for item in items:
        score = _score_knowledge_item(item, query_text, tags)
        if score > 0:
            scored.append((score, item))
    results = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)] or items[:top_k]
    return {"results": [_add_score(item) for item in results[:top_k]]}


def _add_score(item: dict) -> dict:
    result = dict(item)
    result.setdefault("score", 0.0)
    if isinstance(result.get("tags"), str):
        result["tags"] = result["tags"].split(",") if result["tags"] else []
    return result


def _build_where_from_tags(tags: list[str] | None) -> dict | None:
    if not tags:
        return None
    if len(tags) == 1:
        return {"tags": {"$contains": tags[0]}}
    return {"$or": [{"tags": {"$contains": t}} for t in tags]}


def _chroma_to_result(r: dict) -> dict:
    meta = r.get("metadata", {})
    return {
        "id": r.get("id", ""),
        "title": meta.get("title", ""),
        "content": r.get("document", ""),
        "source": meta.get("source", "chroma_vectorstore"),
        "license": meta.get("license", "MIT"),
        "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
        "score": r.get("score", 0.0),
    }


def load_knowledge_cards() -> list[dict]:
    cards: list[dict] = []
    for file_name in KNOWLEDGE_SEED_FILES:
        path = KNOWLEDGE_SEED_DIR / file_name
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as file:
                for line in file:
                    item = _parse_jsonl_line(line)
                    if item:
                        cards.append(item)
        except OSError:
            continue
    return cards


def get_knowledge_source_summary() -> dict:
    cards = load_knowledge_cards()
    active_cards = cards or DEMO_KNOWLEDGE
    categories = sorted({item.get("category", "demo") for item in active_cards})
    sources = sorted({item.get("source", "demo") for item in active_cards})
    licenses = sorted({item.get("license", "MIT") for item in active_cards})
    return {
        "total_cards": len(active_cards),
        "categories": categories,
        "sources": [
            {
                "name": source,
                "license": ",".join(licenses),
                "description": "JSONL 知识卡片" if cards else "内置 Demo 知识卡片",
            }
            for source in sources
        ],
    }


def _parse_jsonl_line(line: str) -> dict | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not all(raw.get(field) for field in ["id", "title", "content"]):
        return None
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    return {
        **raw,
        "tags": [str(tag) for tag in tags],
        "source": raw.get("source", "CodeCoach contributors"),
        "license": raw.get("license", "MIT"),
    }


def _score_knowledge_item(item: dict, query_text: str, tags: list[str] | None = None) -> int:
    haystack = _knowledge_haystack(item)
    title = str(item.get("title", "")).lower()
    item_tags = {str(tag).lower() for tag in item.get("tags", [])}
    tag_text = " ".join(item_tags)
    score = 0
    for token in _query_tokens(query_text):
        normalized = token.lower()
        if token in haystack:
            score += 1
        if normalized in title:
            score += 2
        if normalized in tag_text:
            score += 2
        if normalized in item_tags:
            score += 2
    category = str(item.get("category", ""))
    if category == "algorithm" and any(token in query_text for token in ["递归", "二分", "排序", "查找", "前缀和", "区间和"]):
        score += 2
    if category == "c_mistake" and any(token in query_text for token in ["错误", "越界", "空指针", "野指针", "泄漏", "死循环"]):
        score += 2
    for error_type in ["编译错误", "运行时错误", "逻辑错误"]:
        if error_type in query_text and error_type in title:
            score += 6
    if tags:
        for tag in tags:
            normalized = str(tag).lower()
            if normalized in item_tags or normalized in haystack:
                score += 3
    return score


def _knowledge_haystack(item: dict) -> str:
    parts: list[str] = []
    for value in item.values():
        if isinstance(value, list):
            parts.extend(str(part) for part in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _query_tokens(query_text: str) -> list[str]:
    tokens = [
        "scanf",
        "printf",
        "数组",
        "越界",
        "二分",
        "边界",
        "递归",
        "终止",
        "输入",
        "输出",
        "取地址",
        "初始化",
        "变量",
        "赋值",
        "比较",
        "题目",
        "样例",
        "字符串",
        "空字符",
        "字符数组",
        "函数",
        "参数",
        "指针",
        "地址",
        "空指针",
        "野指针",
        "结构体",
        "联合体",
        "枚举",
        "文件",
        "文件操作",
        "内存",
        "内存泄漏",
        "内存对齐",
        "缓冲区溢出",
        "malloc",
        "free",
        "循环",
        "死循环",
        "switch",
        "case",
        "break",
        "continue",
        "整数除法",
        "浮点",
        "运算符",
        "类型转换",
        "编译错误",
        "运行时错误",
        "逻辑错误",
        "语法错误",
        "链接错误",
        "累计",
        "复杂度",
        "前缀和",
        "区间和",
        "排序",
        "冒泡排序",
        "选择排序",
        "插入排序",
        "快速排序",
        "归并排序",
        "查找",
        "线性查找",
        "二分查找",
    ]
    return [token for token in tokens if token in query_text]
