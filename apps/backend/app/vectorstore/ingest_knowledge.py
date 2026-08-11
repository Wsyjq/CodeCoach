import json
import logging
from pathlib import Path

from app.vectorstore.chroma_client import (
    COLLECTION_KNOWLEDGE,
    COLLECTION_MEMORIES,
    add_documents,
    count_documents,
    delete_collection,
    upsert_documents,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_SEED_DIR = PROJECT_ROOT / "data" / "knowledge_seed"
KNOWLEDGE_SEED_FILES = [
    "c_basics.jsonl",
    "c_mistakes.jsonl",
    "problem_patterns.jsonl",
    "algorithms_c.jsonl",
]


def ingest_knowledge(recreate: bool = False) -> dict:
    if recreate:
        delete_collection(COLLECTION_KNOWLEDGE)

    all_cards = _load_all_cards()
    if not all_cards:
        return {"status": "skipped", "reason": "no knowledge cards found", "total": 0}

    ids = []
    documents = []
    metadatas = []
    for card in all_cards:
        ids.append(card["id"])
        documents.append(_build_embedding_text(card))
        metadatas.append({
            "id": card["id"],
            "title": card.get("title", ""),
            "source": card.get("source", "CodeCoach contributors"),
            "license": card.get("license", "MIT"),
            "category": card.get("category", ""),
            "knowledge_type": card.get("knowledge_type", ""),
            "level": card.get("level", ""),
            "tags": ",".join(card.get("tags", [])),
        })

    ok = add_documents(COLLECTION_KNOWLEDGE, ids, documents, metadatas)
    total = count_documents(COLLECTION_KNOWLEDGE)
    return {
        "status": "ok" if ok else "failed",
        "total_cards_loaded": len(all_cards),
        "total_in_collection": total,
    }


def ingest_learning_memories(memories: list[dict]) -> dict:
    if not memories:
        return {"status": "skipped", "total": 0}
    ids = []
    documents = []
    metadatas = []
    for m in memories:
        ids.append(m["id"])
        documents.append(
            f"标题：{m.get('title', '')}\n"
            f"错误类型：{m.get('error_type', '')}\n"
            f"知识点：{','.join(m.get('knowledge_tags', []))}\n"
            f"错误总结：{m.get('mistake_summary', '')}\n"
            f"复习建议：{m.get('review_tip', '')}"
        )
        metadatas.append({
            "id": m["id"],
            "title": m.get("title", ""),
            "error_type": m.get("error_type", ""),
            "knowledge_tags": ",".join(m.get("knowledge_tags", [])),
        })

    ok = upsert_documents(COLLECTION_MEMORIES, ids, documents, metadatas)
    total = count_documents(COLLECTION_MEMORIES)
    return {
        "status": "ok" if ok else "failed",
        "total_memories_loaded": len(memories),
        "total_in_collection": total,
    }


def _load_all_cards() -> list[dict]:
    cards = []
    for file_name in KNOWLEDGE_SEED_FILES:
        path = KNOWLEDGE_SEED_DIR / file_name
        if not path.exists():
            logger.warning("Knowledge seed file not found: %s", path)
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        card = json.loads(stripped)
                        if all(card.get(field) for field in ["id", "title", "content"]):
                            cards.append(card)
                    except json.JSONDecodeError:
                        logger.warning("Skipping invalid JSONL line in %s", file_name)
        except OSError as e:
            logger.warning("Cannot read %s: %s", path, e)
    return cards


def _build_embedding_text(card: dict) -> str:
    parts = [
        f"标题：{card.get('title', '')}",
        f"分类：{card.get('category', '')}",
        f"标签：{','.join(card.get('tags', []))}",
        f"知识类型：{card.get('knowledge_type', '')}",
        f"正文：{card.get('content', '')}",
    ]
    if card.get("example"):
        parts.append(f"例题：{card['example']}")
    if card.get("common_mistakes"):
        parts.append(f"常见错误：{','.join(card['common_mistakes'])}")
    if card.get("remember_points"):
        parts.append(f"需要记忆：{','.join(card['remember_points'])}")
    if card.get("understand_points"):
        parts.append(f"需要理解：{','.join(card['understand_points'])}")
    return "\n".join(parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = ingest_knowledge(recreate=True)
    print(result)
