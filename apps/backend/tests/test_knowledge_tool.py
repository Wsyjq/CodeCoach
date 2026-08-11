import json

from app.tools import knowledge_tool


def test_loads_project_jsonl_knowledge_cards():
    cards = knowledge_tool.load_knowledge_cards()

    assert len(cards) >= 17
    assert any(card["id"] == "c_scanf_001" for card in cards)
    assert all(isinstance(card["tags"], list) for card in cards)
    assert all(card["source"] == "CodeCoach contributors" for card in cards)
    assert all(card["license"] == "MIT" for card in cards)


def test_search_knowledge_base_uses_jsonl_cards(monkeypatch):
    monkeypatch.setattr(knowledge_tool, "search_similar", lambda *args, **kwargs: [])

    results = knowledge_tool.search_knowledge_base("递归 为什么要有 终止 条件", top_k=1)

    assert results["results"][0]["id"] == "algo_recursion_001"


def test_search_knowledge_base_matches_scanf_card():
    results = knowledge_tool.search_knowledge_base("scanf 为什么要加 & 取地址", top_k=1)

    assert results["results"][0]["id"] == "c_scanf_001"
    assert "scanf" in results["results"][0]["tags"]


def test_search_knowledge_base_uses_tag_boosting():
    results = knowledge_tool.search_knowledge_base("边界", top_k=1, tags=["二分查找"])

    assert results["results"][0]["id"] == "algo_binary_search_001"


def test_search_knowledge_base_falls_back_to_demo_when_jsonl_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(knowledge_tool, "KNOWLEDGE_SEED_DIR", tmp_path)

    results = knowledge_tool.search_knowledge_base("scanf", top_k=1)

    assert results["results"][0]["id"] == "c_scanf_001"


def test_load_knowledge_cards_skips_invalid_jsonl_lines(monkeypatch, tmp_path):
    seed_dir = tmp_path / "knowledge_seed"
    seed_dir.mkdir()
    valid_card = {
        "id": "valid_card",
        "title": "有效知识卡",
        "content": "数组 边界 知识",
        "tags": ["数组"],
    }
    (seed_dir / "c_basics.jsonl").write_text(
        "not json\n" + json.dumps(valid_card, ensure_ascii=False) + "\n{}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(knowledge_tool, "KNOWLEDGE_SEED_DIR", seed_dir)

    cards = knowledge_tool.load_knowledge_cards()

    assert [card["id"] for card in cards] == ["valid_card"]


def test_knowledge_source_summary_reflects_loaded_cards():
    summary = knowledge_tool.get_knowledge_source_summary()

    assert summary["total_cards"] >= 17
    assert "c_basic" in summary["categories"]
    assert summary["sources"]
    assert summary["sources"][0]["name"]


def test_search_knowledge_base_matches_prefix_sum_card():
    results = knowledge_tool.search_knowledge_base("前缀和 怎么求 区间和", top_k=1)

    assert results["results"][0]["id"] == "algo_prefix_sum_001"


def test_search_knowledge_base_matches_string_card():
    results = knowledge_tool.search_knowledge_base("字符串 为什么要有 空字符", top_k=1)

    assert results["results"][0]["id"] == "c_string_null_001"


def test_search_knowledge_base_matches_structure_card(monkeypatch):
    monkeypatch.setattr(knowledge_tool, "search_similar", lambda *args, **kwargs: [])

    results = knowledge_tool.search_knowledge_base("结构体 成员访问 内存对齐", top_k=5)

    assert any(result["id"] == "c_struct_member_001" for result in results["results"])


def test_search_knowledge_base_matches_runtime_error_card(monkeypatch):
    monkeypatch.setattr(knowledge_tool, "search_similar", lambda *args, **kwargs: [])

    results = knowledge_tool.search_knowledge_base("运行时错误 空指针 野指针 内存泄漏", top_k=5)

    assert any(result["id"] == "c_runtime_pointer_001" for result in results["results"])
