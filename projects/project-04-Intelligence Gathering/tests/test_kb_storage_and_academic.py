# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pytest

import config
from media_platform.research.core import _extract_repository_urls, _inverted_abstract, _paper_id
from tools.async_file_writer import AsyncFileWriter
from tools.kb_paths import platform_from_relative_path


@pytest.fixture
def isolated_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SAVE_DATA_PATH", str(tmp_path))
    monkeypatch.setattr(config, "KB_NAMESPACE", "course-kb")
    return tmp_path


def test_sources_are_stored_in_separate_kb_categories(isolated_storage):
    arxiv_path = AsyncFileWriter("arxiv", "search")._get_file_path("jsonl", "papers").replace("\\", "/")
    github_path = AsyncFileWriter("github", "search")._get_file_path("jsonl", "repositories").replace("\\", "/")
    zhihu_path = AsyncFileWriter("zhihu", "search")._get_file_path("jsonl", "contents").replace("\\", "/")

    assert "/kb/course-kb/papers/arxiv/jsonl/" in arxiv_path
    assert "_papers_" in arxiv_path
    assert "/kb/course-kb/repositories/github/jsonl/" in github_path
    assert "_repositories_" in github_path
    assert "/kb/course-kb/platforms/zhihu/jsonl/" in zhihu_path
    assert "_contents_" in zhihu_path


def test_platform_inference_supports_new_and_legacy_layouts():
    assert platform_from_relative_path("kb/course-kb/papers/openalex/jsonl/search_papers.jsonl") == "openalex"
    assert platform_from_relative_path("kb/course-kb/repositories/github/jsonl/search_repositories.jsonl") == "github"
    assert platform_from_relative_path("github/jsonl/search_contents.jsonl") == "github"


def test_openalex_abstract_is_reconstructed_in_position_order():
    assert _inverted_abstract({"MCP": [0, 2], "security": [1], "matters": [3]}) == "MCP security MCP matters"
    assert _inverted_abstract(None) == ""


def test_repository_urls_are_extracted_and_cleaned():
    text = "Code: https://github.com/example/mcp-tool.git. Mirrors at https://gitlab.com/example/mirror and https://github.com/features/actions"
    assert _extract_repository_urls(text) == [
        "https://github.com/example/mcp-tool",
        "https://gitlab.com/example/mirror",
    ]


def test_paper_id_is_filesystem_safe():
    assert _paper_id("http://arxiv.org/abs/2509.12345v1") == "2509.12345v1"
    assert _paper_id("https://openalex.org/W123456789") == "W123456789"


@pytest.mark.asyncio
async def test_linked_paper_sidecar_is_stored_with_papers(isolated_storage):
    writer = AsyncFileWriter("arxiv", "search")
    await writer.write_linked_paper("2509.12345v1", {
        "paper": {"title": "MCP security", "url": "http://arxiv.org/abs/2509.12345v1"},
        "repositories": [{"full_name": "example/mcp-tool", "url": "https://github.com/example/mcp-tool"}],
    })

    sidecar = Path(isolated_storage) / "kb" / "course-kb" / "papers" / "arxiv" / "linked_repositories" / "2509.12345v1.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["repositories"][0]["full_name"] == "example/mcp-tool"
