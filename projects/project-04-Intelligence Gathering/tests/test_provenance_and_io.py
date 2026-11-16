# -*- coding: utf-8 -*-
import json

import pipeline.analysis_service as analysis_service
import pipeline.research_intelligence as research_intelligence
from pipeline.io_utils import atomic_write_lines, atomic_write_text


def _item(platform: str) -> dict:
    return {
        "title": "同一篇内容",
        "text": "这是一段用于验证跨来源去重与溯源记录的正文。" * 20,
        "source_url": "https://example.com/article/1",
        "source_platform": platform,
        "source_quality": 0.9,
        "content_type": "research",
        "research_domains": ["RAG 安全"],
        "evidence": ["这是一条可核验的原文证据，长度足够用于归档筛选。"],
        "quality_score": 0.9,
        "keywords": ["rag", "安全"],
    }


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(research_intelligence, "DATA_DIR", tmp_path)
    monkeypatch.setattr(research_intelligence, "DB_PATH", tmp_path / "research.sqlite")
    monkeypatch.setattr(research_intelligence, "sync_obsidian", lambda: {"status": "skipped"})


def test_duplicate_content_keeps_first_source_and_records_every_observation(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    first = "arxiv/search_a_contents_2026-01-01.jsonl"
    second = "github/search_b_contents_2026-01-02.jsonl"
    research_intelligence.ingest_analysis(first, "analysis/a.jsonl", [_item("arxiv")], {})
    research_intelligence.ingest_analysis(second, "analysis/b.jsonl", [_item("github")], {})

    with research_intelligence._connect() as conn:
        documents = conn.execute("SELECT source_file, platform FROM documents").fetchall()
        observations = conn.execute(
            "SELECT source_file, platform FROM crawl_observations ORDER BY observed_at"
        ).fetchall()

    assert len(documents) == 1
    assert documents[0]["source_file"] == first
    assert documents[0]["platform"] == "arxiv"
    assert [(row["source_file"], row["platform"]) for row in observations] == [
        (first, "arxiv"),
        (second, "github"),
    ]

    snapshot = research_intelligence.context_snapshot(limit=10)
    record = snapshot["documents"][0]
    assert record["source_count"] == 2
    assert {source["source_file"] for source in record["sources"]} == {first, second}


def test_normalize_keeps_merged_source_metadata():
    normalized = analysis_service._normalize({
        "title": "标题",
        "content": "正文",
        "__source_file": "arxiv/search_a_contents_2026-01-01.jsonl",
        "__source_platform": "arxiv",
    })

    assert normalized["source_file"] == "arxiv/search_a_contents_2026-01-01.jsonl"
    assert normalized["source_platform"] == "arxiv"


def test_merged_batch_keeps_each_records_original_source(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    original = "arxiv/search_a_contents_2026-01-01.jsonl"
    item = {**_item("arxiv"), "source_file": original}

    research_intelligence.ingest_analysis(
        "analysis/batch_inputs/merged_20260101_120000_1files.jsonl",
        "analysis/batch_inputs/merged.jsonl",
        [item],
        {},
    )

    with research_intelligence._connect() as conn:
        document = conn.execute("SELECT source_file FROM documents").fetchone()
        observation = conn.execute("SELECT source_file FROM crawl_observations").fetchone()

    assert document["source_file"] == original
    assert observation["source_file"] == original


def test_linked_repositories_are_persisted_with_paper(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    item = {**_item("arxiv"), "linked_repositories": [{"full_name": "example/mcp-tool", "url": "https://github.com/example/mcp-tool"}]}

    research_intelligence.ingest_analysis("arxiv/papers.jsonl", "analysis/paper.jsonl", [item], {})

    record = research_intelligence.context_snapshot(limit=10)["documents"][0]
    assert record["linked_repositories"][0]["full_name"] == "example/mcp-tool"


def test_atomic_write_text_skips_unchanged_content(tmp_path):
    target = tmp_path / "notes" / "a.md"

    assert atomic_write_text(target, "第一版") is True
    assert atomic_write_text(target, "第一版") is False
    assert target.read_text(encoding="utf-8") == "第一版"
    assert [path.name for path in target.parent.iterdir()] == ["a.md"]


def test_atomic_write_lines_replaces_target(tmp_path):
    target = tmp_path / "batch.jsonl"

    atomic_write_lines(target, ['{"a": 1}\n'])
    atomic_write_lines(target, ['{"a": 2}\n', '{"a": 3}\n'])

    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"a": 2}, {"a": 3}]
    assert [path.name for path in target.parent.iterdir()] == ["batch.jsonl"]


def test_merged_input_names_do_not_collide_within_one_second(monkeypatch, tmp_path):
    monkeypatch.setattr(analysis_service, "DATA_DIR", tmp_path)
    monkeypatch.setattr(analysis_service, "ANALYSIS_DIR", tmp_path / "analysis")
    source = tmp_path / "arxiv" / "search_x_contents_2026-01-01.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"title": "t", "content": "c"}, ensure_ascii=False) + "\n", encoding="utf-8")

    first = analysis_service.prepare_merged_input(["arxiv/search_x_contents_2026-01-01.jsonl"], 10)
    second = analysis_service.prepare_merged_input(["arxiv/search_x_contents_2026-01-01.jsonl"], 10)

    assert first != second
