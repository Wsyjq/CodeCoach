from app.vectorstore import chroma_client


class FakeCollection:
    def __init__(self):
        self.add_calls = []
        self.upsert_calls = []

    def add(self, **kwargs):
        self.add_calls.append(kwargs)

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)


class FailingCollection:
    def add(self, **kwargs):
        raise RuntimeError("add failed")

    def upsert(self, **kwargs):
        raise RuntimeError("upsert failed")


def test_get_client_returns_none_when_chromadb_is_unavailable(monkeypatch):
    monkeypatch.setattr(chroma_client, "_chromadb", None)
    monkeypatch.setattr(chroma_client, "_client", None)

    assert chroma_client._get_client() is None


def test_add_documents_calls_chroma_add(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(chroma_client, "get_collection", lambda name: collection)

    ok = chroma_client.add_documents(
        "knowledge_chunks",
        ["doc_1"],
        ["scanf 需要地址"],
        [{"title": "scanf"}],
    )

    assert ok is True
    assert collection.add_calls == [
        {
            "ids": ["doc_1"],
            "documents": ["scanf 需要地址"],
            "metadatas": [{"title": "scanf"}],
        }
    ]
    assert collection.upsert_calls == []


def test_add_documents_returns_false_when_collection_unavailable(monkeypatch):
    monkeypatch.setattr(chroma_client, "get_collection", lambda name: None)

    ok = chroma_client.add_documents("knowledge_chunks", ["doc_1"], ["content"])

    assert ok is False


def test_add_documents_returns_false_when_chroma_add_fails(monkeypatch):
    monkeypatch.setattr(chroma_client, "get_collection", lambda name: FailingCollection())

    ok = chroma_client.add_documents("knowledge_chunks", ["doc_1"], ["content"])

    assert ok is False


def test_upsert_documents_calls_chroma_upsert(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(chroma_client, "get_collection", lambda name: collection)

    ok = chroma_client.upsert_documents(
        "learning_memories",
        ["review_1"],
        ["数组越界复盘"],
        [{"title": "数组越界"}],
    )

    assert ok is True
    assert collection.add_calls == []
    assert collection.upsert_calls == [
        {
            "ids": ["review_1"],
            "documents": ["数组越界复盘"],
            "metadatas": [{"title": "数组越界"}],
        }
    ]


def test_upsert_documents_returns_false_when_collection_unavailable(monkeypatch):
    monkeypatch.setattr(chroma_client, "get_collection", lambda name: None)

    ok = chroma_client.upsert_documents("learning_memories", ["review_1"], ["content"])

    assert ok is False


def test_upsert_documents_returns_false_when_chroma_upsert_fails(monkeypatch):
    monkeypatch.setattr(chroma_client, "get_collection", lambda name: FailingCollection())

    ok = chroma_client.upsert_documents("learning_memories", ["review_1"], ["content"])

    assert ok is False
