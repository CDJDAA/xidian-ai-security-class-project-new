import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coursework import arxiv_smoke as smoke  # noqa: E402
from research_agent.arxiv_metadata import normalize_arxiv_id  # noqa: E402


def test_aliases_share_one_request_and_independent_results(monkeypatch):
    calls = []
    monkeypatch.setattr(smoke.time, "sleep", lambda _: pytest.fail("Cache hit slept"))

    def lookup(identifier):
        calls.append(identifier)
        return {"arxiv_id": identifier, "authors": ["Author"]}

    results = smoke.lookup_references(
        ["2410.07283v1", "https://arxiv.org/pdf/2410.07283v1.pdf", "2410.07283v1"],
        lookup, normalize_arxiv_id,
    )
    assert calls == ["2410.07283v1"]
    assert [reused for _, reused, _ in results] == [False, True, True]
    results[0][0]["authors"].append("Changed")
    assert results[1][0]["authors"] == ["Author"]


def test_revisions_remain_separate_and_requests_are_spaced(monkeypatch):
    sleeps = []
    calls = []
    monkeypatch.setattr(smoke.time, "monotonic", lambda: 10)
    monkeypatch.setattr(smoke.time, "sleep", sleeps.append)
    smoke.lookup_references(["2410.07283v1", "2410.07283v2", "2410.07283"],
                            lambda value: calls.append(value) or {"id": value}, normalize_arxiv_id)
    assert calls == ["2410.07283v1", "2410.07283v2", "2410.07283"]
    assert sleeps == [3, 3]


def test_failure_is_not_cached(monkeypatch):
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    responses = iter([None, {"id": "2410.07283v1"}])
    results = smoke.lookup_references(["2410.07283v1"] * 2, lambda _: next(responses), normalize_arxiv_id)
    assert results[0][0] is None
    assert results[1][0] is not None
    assert not results[1][1]


def test_invalid_batch_makes_no_requests():
    with pytest.raises(ValueError):
        smoke.lookup_references(["2410.07283v1", "bad"],
                                lambda _: pytest.fail("Unexpected request"), normalize_arxiv_id)


def test_cache_does_not_survive_batches():
    calls = []
    for _ in range(2):
        smoke.lookup_references(["2410.07283"], lambda value: calls.append(value) or {}, normalize_arxiv_id)
    assert len(calls) == 2


def test_completed_result_checkpoint_survives_later_interruption(monkeypatch):
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    saved = []
    def lookup(value):
        if value.endswith("v2"):
            raise KeyboardInterrupt
        return {"id": value}
    with pytest.raises(KeyboardInterrupt):
        smoke.lookup_references(["2410.07283v1", "2410.07283v2"], lookup, normalize_arxiv_id,
                                on_result=lambda *row: saved.append(row))
    assert len(saved) == 1
    assert saved[0][1]["id"] == "2410.07283v1"
