import importlib.util
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_agent import arxiv_metadata as metadata  # noqa: E402

FEED = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/2410.07283v1</id><title>Fixture paper</title>
<summary>Fixture abstract.</summary><author><name>Test author</name></author>
<published>2024-10-09T00:00:00Z</published><updated>2024-10-09T00:00:00Z</updated>
<category term="cs.AI"/></entry></feed>'''


@pytest.mark.parametrize("value,expected", [
    ("2410.07283v1", "2410.07283v1"), ("2410.07283", "2410.07283"),
    ("https://arxiv.org/pdf/2410.07283v1.pdf", "2410.07283v1"),
    ("https://arxiv.org/abs/hep-th/9901001v2", "hep-th/9901001v2"),
])
def test_revision_and_legacy_identity_are_preserved(value, expected):
    assert metadata.normalize_arxiv_id(value) == expected


@pytest.mark.parametrize("value", ["https://arxiv.org.evil.test/abs/2410.07283", "https://name:secret@arxiv.org/abs/2410.07283", "../../secret", "2410.07283v0", "https://arxiv.org/abs/2410.07283?bad=1"])
def test_invalid_identifier_is_rejected(value):
    with pytest.raises(ValueError):
        metadata.normalize_arxiv_id(value)


def test_source_dates_and_content_hash_are_retained():
    result = metadata.parse_metadata(FEED, "2410.07283v1")
    assert result["arxiv_id"] == "2410.07283v1"
    assert result["version"] == "1"
    assert result["published"].tzinfo is not None
    assert len(result["provenance"]["response_sha256"]) == 64


@pytest.mark.parametrize("requested", ["2410.07283v2", "2406.13352v1"])
def test_wrong_version_or_paper_cannot_pass_as_requested(requested):
    with pytest.raises(ValueError, match="different"):
        metadata.parse_metadata(FEED, requested)


def test_request_preserves_revision_and_uses_a_timeout(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return FEED
    def opener(request, timeout):
        assert "id_list=2410.07283v1" in request.full_url
        assert request.full_url.startswith("https://export.arxiv.org/api/query?")
        assert timeout == 7
        return Response()
    monkeypatch.setattr(metadata, "urlopen", opener)
    assert metadata.fetch_arxiv_metadata("2410.07283v1", timeout=7)["version"] == "1"


def test_original_tool_retains_its_none_error_contract(monkeypatch):
    spec = importlib.util.spec_from_file_location("reference_tool", ROOT / "research_agent/inno/tools/inno_tools/paper_search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def unavailable(identifier): raise URLError("fixture failure")
    monkeypatch.setattr(module, "fetch_arxiv_metadata", unavailable)
    assert module.get_arxiv_paper_meta("2410.07283v1") is None
