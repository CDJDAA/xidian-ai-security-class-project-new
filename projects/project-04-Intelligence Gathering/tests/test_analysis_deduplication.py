"""Regression evidence for the course deduplication extension (see LICENSE)."""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

with patch("dotenv.load_dotenv"):
    from pipeline import analysis_service as analysis
    from pipeline import research_intelligence as store
from pipeline.content_identity import content_fingerprint, stored_fingerprint


def legacy_fingerprint(item):
    source = f"{item['title']}\n{item['text']}\n{item['source_url']}"
    return hashlib.sha1(re.sub(r"\s+", " ", source).strip().encode()).hexdigest()


@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(analysis.jieba.dt, "tmp_dir", str(data))
    vault = tmp_path / "academic"
    (vault / "30-来源" / "自动采集").mkdir(parents=True)
    monkeypatch.setattr(analysis, "DATA_DIR", data)
    monkeypatch.setattr(analysis, "ANALYSIS_DIR", data / "analysis")
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "DB_PATH", data / "research_intelligence.sqlite")
    monkeypatch.setenv("AI_API_KEY", "")
    monkeypatch.setenv("OBSIDIAN_ACADEMIC_VAULT_PATH", str(vault))
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.setenv("OBSIDIAN_SOCIAL_VAULT_PATH", "")
    # Separate run IDs without sleeping; production timestamps have second precision.
    ticks = iter(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=i) for i in range(1000))
    monkeypatch.setattr(store, "_now_text", lambda: next(ticks).isoformat())
    return data, vault


def long_rows():
    prefix = "semantic drift evidence. " * 200
    return [{"title": "semantic drift", "content": prefix + ending, "url": "https://example.org/paper"}
            for ending in ("Different ending A", "Different ending B")]


def test_old_collision_is_reproduced_and_fixed():
    first, second = map(analysis._normalize, long_rows())
    assert first["text"] == second["text"]
    assert legacy_fingerprint(first) == legacy_fingerprint(second)
    assert analysis._fingerprint(first) != analysis._fingerprint(second)


@pytest.mark.parametrize("field,prefix", [("title", "t" * 500), ("content", "c" * 4000), ("url", "https://example.org/" + "u" * 1000)])
def test_differences_after_display_limit_survive(field, prefix):
    row = {"title": "title", "content": "text", "url": "https://example.org"}
    assert analysis._fingerprint(analysis._normalize({**row, field: prefix + "A"})) != analysis._fingerprint(analysis._normalize({**row, field: prefix + "B"}))


def test_whitespace_and_field_boundaries():
    assert content_fingerprint("a\n b", "c\t d", " url ") == content_fingerprint("a b", "c d", "url")
    assert content_fingerprint("a", "b c", "url") != content_fingerprint("a b", "c", "url")
    assert content_fingerprint("a", "b", "url1") != content_fingerprint("a", "b", "url2")


def run_rows(data, rows):
    path = data / "arxiv" / "jsonl" / "sample.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return asyncio.run(analysis.analyze_file("arxiv/jsonl/sample.jsonl", selected_themes=[], custom_themes=["semantic drift"]))


def test_counts_and_archive_integration(isolated_pipeline):
    data, vault = isolated_pipeline
    rows = long_rows()
    rows += [rows[0].copy(), {**rows[0], "title": " semantic   drift "}, {}, {"title": "unrelated", "content": "unrelated"}]
    meta = run_rows(data, rows)
    assert (meta["input_count"], meta["output_count"], meta["duplicate_count"], meta["empty_count"], meta["scope_excluded"]) == (6, 2, 2, 1, 1)
    assert meta["fingerprint_version"] == "v2:sha256"
    assert not meta["ai_enabled"]
    items = analysis._read_rows(data / meta["output_file"], 100)
    with store._connect() as conn:
        documents = conn.execute("SELECT * FROM documents").fetchall()
    assert len(documents) == 2
    assert {d["fingerprint"] for d in documents} == {i["content_fingerprint"] for i in items}
    notes = list(vault.rglob("文献-*.md"))
    assert len(notes) == 2
    for document in documents:
        assert any(document["id"] in note.read_text(encoding="utf-8") for note in notes)
    store.ingest_analysis(meta["source_file"], "analysis/reimport.jsonl", items, meta["intelligence"])
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM documents").fetchone()[0] == 2


def test_legacy_import_retains_identity(isolated_pipeline):
    item = analysis._rule_analysis(analysis._normalize(long_rows()[0]), {"semantic drift": ["semantic drift"]})
    item.pop("content_fingerprint")
    item["source_platform"] = "arxiv"
    expected = hashlib.sha1(f"{item['title'].strip()}\n{item['text'].strip()}\n{item['source_url'].strip()}".encode()).hexdigest()
    assert stored_fingerprint(item) == expected
    store.ingest_analysis("arxiv/legacy.jsonl", "analysis/legacy.jsonl", [item], {})
    with store._connect() as conn:
        assert conn.execute("SELECT fingerprint FROM documents").fetchone()[0] == expected


@pytest.mark.parametrize("value", ["", "v2:sha256:bad", "v3:unknown", 123])
def test_invalid_identity_is_not_silently_accepted(value):
    with pytest.raises(ValueError):
        stored_fingerprint({"content_fingerprint": value})
