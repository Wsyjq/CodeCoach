from __future__ import annotations

import logging
import os
from threading import RLock
from pathlib import Path
from typing import Any

try:
    import chromadb as _chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    _chromadb = None
    ChromaSettings = None

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
_configured_vectorstore_dir = os.getenv("CODECOACH_VECTORSTORE_DIR", "").strip()
VECTORSTORE_DIR = (
    Path(_configured_vectorstore_dir)
    if _configured_vectorstore_dir
    else PROJECT_ROOT / "data" / "runtime" / "vectorstore"
)
COLLECTION_KNOWLEDGE = "knowledge_chunks"
COLLECTION_MEMORIES = "learning_memories"

_client = None
_collections: dict[str, Any] = {}
_client_lock = RLock()
_collection_lock = RLock()


def _get_client():
    global _client
    if _chromadb is None or ChromaSettings is None:
        logger.debug("ChromaDB is not installed; using local JSONL search")
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        try:
            VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
            _client = _chromadb.PersistentClient(
                path=str(VECTORSTORE_DIR),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info("ChromaDB client initialized at %s", VECTORSTORE_DIR)
            return _client
        except Exception as e:
            logger.warning("ChromaDB init failed: %s", e)
            return None


def get_collection(name: str) -> Any | None:
    if name in _collections:
        return _collections[name]
    with _collection_lock:
        if name in _collections:
            return _collections[name]
        client = _get_client()
        if client is None:
            return None
        try:
            collection = client.get_or_create_collection(name=name)
            _collections[name] = collection
            return collection
        except Exception as e:
            logger.warning("ChromaDB get_collection(%s) failed: %s", name, e)
            return None


def add_documents(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict] | None = None,
) -> bool:
    collection = get_collection(collection_name)
    if collection is None:
        return False
    try:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Added %d docs to ChromaDB '%s'", len(ids), collection_name)
        return True
    except Exception as e:
        logger.warning("ChromaDB add failed: %s", e)
        return False


def upsert_documents(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict] | None = None,
) -> bool:
    collection = get_collection(collection_name)
    if collection is None:
        return False
    try:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Upserted %d docs to ChromaDB '%s'", len(ids), collection_name)
        return True
    except Exception as e:
        logger.warning("ChromaDB upsert failed: %s", e)
        return False


def search_similar(
    collection_name: str,
    query: str,
    top_k: int = 3,
    where: dict | None = None,
) -> list[dict]:
    collection = get_collection(collection_name)
    if collection is None:
        return []
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        return _format_results(results)
    except Exception as e:
        logger.warning("ChromaDB search failed: %s", e)
        return []


def count_documents(collection_name: str) -> int:
    collection = get_collection(collection_name)
    if collection is None:
        return 0
    try:
        return collection.count()
    except Exception as e:
        logger.warning("ChromaDB count failed: %s", e)
        return 0


def delete_collection(name: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.delete_collection(name=name)
        _collections.pop(name, None)
        logger.info("Deleted ChromaDB collection '%s'", name)
        return True
    except Exception as e:
        logger.warning("ChromaDB delete_collection failed: %s", e)
        return False


def _format_results(results: dict) -> list[dict]:
    formatted = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for i, doc_id in enumerate(ids):
        formatted.append(
            {
                "id": doc_id,
                "document": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "score": 1.0 - (distances[i] if i < len(distances) else 0.0),
            }
        )
    return formatted
