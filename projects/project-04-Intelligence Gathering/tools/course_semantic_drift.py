"""Reproduce project 04 in a private, ignored workspace. See LICENSE.

Run from the project root: python tools/course_semantic_drift.py
No .env is loaded; AI and user knowledge vaults are never used.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import httpx

# Suppress both config and analysis import-time dotenv loading.
with patch("dotenv.load_dotenv"):
    import config
    from media_platform.research.core import ArxivCrawler, GithubCrawler
    from pipeline import analysis_service as analysis
    from pipeline import research_intelligence as store

QUERY = "semantic drift"


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def legacy_key(item):
    text = f"{item['title']}\n{item['text']}\n{item['source_url']}"
    return hashlib.sha1(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()


def baseline(rows, source_platform):
    """Reproduce the old analysis filtering on the exact same collected snapshot."""
    seen, items = set(), []
    counts = {"input_count": len(rows), "duplicate_count": 0, "empty_count": 0, "scope_excluded": 0}
    for row in rows:
        item = analysis._normalize(row)
        item["source_platform"] = source_platform
        if not (item["title"] or item["text"]):
            counts["empty_count"] += 1
            continue
        key = legacy_key(item)
        if key in seen:
            counts["duplicate_count"] += 1
            continue
        seen.add(key)
        enriched = analysis._rule_analysis(item, {QUERY: [QUERY]})
        if not enriched["research_domains"]:
            counts["scope_excluded"] += 1
            continue
        items.append(enriched)
    return {**counts, "output_count": len(items)}


def api_records(attempts, root, source_platform):
    """Independently parse the saved HTTP response for provenance checks."""
    records = {}
    for attempt in attempts:
        if attempt.get("status_code") != 200 or not attempt.get("response_file"):
            continue
        text = (root / attempt["response_file"]).read_text(encoding="utf-8")
        if source_platform == "arxiv" and "export.arxiv.org" in attempt["url"]:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in ET.fromstring(text).findall("a:entry", ns):
                clean = lambda key: " ".join((entry.findtext(f"a:{key}", default="", namespaces=ns)).split())
                records[clean("id")] = {"title": clean("title"), "content": clean("summary")}
        elif source_platform == "github" and "api.github.com/search/repositories" in attempt["url"]:
            for repo in json.loads(text).get("items", []):
                records[repo["html_url"]] = {"title": repo["full_name"], "content": repo.get("description") or ""}
    return records


async def collect(root, manifest):
    original_client = httpx.AsyncClient

    async def record_response(response):
        await response.aread()
        name = f"response-{len(manifest['requests']) + 1}.txt"
        (root / name).write_text(response.text, encoding="utf-8")
        manifest["requests"].append({"time_utc": now(), "method": response.request.method,
                                     "url": str(response.request.url), "status_code": response.status_code,
                                     "response_file": name})

    class RecordingClient(original_client):
        def __init__(self, *args, **kwargs):
            kwargs["event_hooks"] = {"response": [record_response]}
            super().__init__(*args, **kwargs)

    for adapter_type in (ArxivCrawler, GithubCrawler):
        crawler = adapter_type()
        rows = []

        async def capture(item, item_type="contents"):
            rows.append(item)

        crawler._write = capture
        attempt = {"platform": crawler.platform, "started_at_utc": now()}
        manifest["collection_attempts"].append(attempt)
        print(f"Collecting {crawler.platform}: {QUERY}, limit=10", flush=True)
        try:
            with patch("httpx.AsyncClient", RecordingClient):
                await crawler.search()
            if not rows:
                raise ValueError("No records returned")
        except (httpx.HTTPError, ValueError) as error:
            # No request headers, tokens, cookies or exception response bodies are logged.
            attempt["failure"] = type(error).__name__
            if isinstance(error, httpx.HTTPStatusError):
                attempt["status_code"] = error.response.status_code
            print(f"{crawler.platform} unavailable: {attempt['failure']}", flush=True)
            continue
        attempt["record_count"] = len(rows)
        return crawler.platform, rows
    raise RuntimeError("Both public adapters failed; see local manifest.json")


async def run(root, manifest):
    data = root / "data"
    vault = root / "academic"
    data.mkdir()
    (vault / "30-来源" / "自动采集").mkdir(parents=True)
    os.environ.update({"AI_API_KEY": "", "AI_BATCH_SIZE": "50", "GITHUB_TOKEN": "",
                       "OBSIDIAN_ACADEMIC_VAULT_PATH": str(vault), "OBSIDIAN_VAULT_PATH": str(vault),
                       "OBSIDIAN_SOCIAL_VAULT_PATH": ""})
    config.KEYWORDS, config.CRAWLER_MAX_NOTES_COUNT = QUERY, 10
    config.CRAWLER_MAX_SLEEP_SEC, config.GITHUB_TOKEN = 3, ""
    analysis.DATA_DIR, analysis.ANALYSIS_DIR = data, data / "analysis"
    analysis.jieba.dt.tmp_dir = str(root)
    store.DATA_DIR, store.DB_PATH = data, data / "research_intelligence.sqlite"
    source_platform, rows = await collect(root, manifest)
    relative = f"{source_platform}/jsonl/semantic_drift.jsonl"
    raw = data / relative
    raw.parent.mkdir(parents=True)
    raw.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest.update({"platform": source_platform, "raw_file": str(raw.relative_to(root)),
                     "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "before": baseline(rows, source_platform)})
    meta = await analysis.analyze_file(relative, limit=10, selected_themes=[], custom_themes=[QUERY])
    items = analysis._read_rows(data / meta["output_file"], 10)
    manifest["after"] = meta
    with sqlite3.connect(store.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        docs = {row["fingerprint"]: dict(row) for row in conn.execute("SELECT * FROM documents")}
    notes = [(str(path.relative_to(root)), path.read_text(encoding="utf-8")) for path in vault.rglob("文献-*.md")]
    originals = api_records(manifest["requests"], root, source_platform)
    analyzed = {item["content_fingerprint"]: item for item in items}
    verification, seen = [], set()
    for line, row in enumerate(rows, 1):
        normalized = analysis._normalize(row)
        key = normalized["content_fingerprint"]
        item = analyzed.get(key)
        duplicate = key in seen
        seen.add(key)
        curated = bool(item and store._is_curated({**item, "source_file": relative}))
        doc = docs.get(key)
        matched_notes = [name for name, text in notes if doc and doc["id"] in text and doc["source_url"] in text]
        original = originals.get(row["url"])
        expected_summary = normalized["text"][:240] + ("…" if len(normalized["text"]) > 240 else "")
        entry = {"raw_line": line, "title": row["title"], "url": row["url"], "content_fingerprint": key,
                 "api_source_matches": original == {"title": row["title"], "content": row["content"]},
                 "filter_result": "duplicate" if duplicate else ("included" if item else "scope_excluded"),
                 "curated": curated,
                 "archive_reason": "analyzed academic record" if item else "excluded before ingestion",
                 "summary_matches": item["summary"] == expected_summary if item else None,
                 "raw_preserved": item["raw"] == row if item else None,
                 "document_id": doc["id"] if doc else None, "archive_files": matched_notes,
                 "human_review": "pending"}
        verification.append(entry)
        if not entry["api_source_matches"] or (item and (not entry["summary_matches"] or not entry["raw_preserved"] or not doc or not matched_notes)):
            raise AssertionError(f"Source/analysis/archive mismatch at raw line {line}")
    manifest["verification"] = verification
    manifest["document_count"] = len(docs)
    manifest["archive_count"] = len(notes)
    # Existing run IDs use whole seconds. Keep real timestamps and separate the
    # immediate reimport by a second instead of rewriting production identity.
    await asyncio.sleep(1.1)
    store.ingest_analysis(relative, "analysis/reimport.jsonl", items, meta["intelligence"])
    with sqlite3.connect(store.DB_PATH) as conn:
        manifest["reimport_document_count"] = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
    assert manifest["reimport_document_count"] == len(docs)
    prefix = "semantic drift evidence. " * 200
    synthetic = [analysis._normalize({"title": QUERY, "content": prefix + end, "url": "https://example.org/paper"}) for end in ("A", "B")]
    manifest["synthetic_long_text"] = {"input_count": 2, "legacy_unique": len({legacy_key(i) for i in synthetic}),
                                        "fixed_unique": len({analysis._fingerprint(i) for i in synthetic})}
    assert manifest["synthetic_long_text"] == {"input_count": 2, "legacy_unique": 1, "fixed_unique": 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    # Fixed output parent prevents accidental writes into a personal vault.
    root = PROJECT_ROOT / "data" / "course_semantic_drift" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    if os.name == "nt":
        # The existing exporter includes paper titles in filenames; deep Windows
        # checkouts can exceed MAX_PATH even with bounded titles.
        root = Path("\\\\?\\" + str(root))
    root.mkdir(parents=True, exist_ok=False)
    manifest = {"started_at_utc": now(), "query": QUERY, "limit": 10, "ai_enabled": False,
                "environment": {"python": sys.version, "platform": platform.platform(),
                                "packages": {name: importlib.metadata.version(name) for name in ("httpx", "jieba", "pytest", "python-dotenv")}},
                "collection_attempts": [], "requests": []}
    try:
        asyncio.run(run(root, manifest))
        manifest["status"] = "completed"
    except Exception as error:
        manifest["status"], manifest["error_type"] = "failed", type(error).__name__
        raise
    finally:
        manifest["finished_at_utc"] = now()
        write_json(root / "manifest.json", manifest)
        print(f"Local manifest: {root / 'manifest.json'}", flush=True)


if __name__ == "__main__":
    main()
