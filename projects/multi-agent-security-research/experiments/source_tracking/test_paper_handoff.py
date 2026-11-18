import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECTS = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, PROJECTS / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load("evidence_audit", "project-02-ai-scientist-v2/ai_scientist/evidence_audit.py")
citation = load("standalone_citation", "project-03-deeptutor/deeptutor/agents/research/utils/citation_manager.py")


@pytest.fixture
def results():
    return json.loads(Path(__file__).with_name("results_v2.json").read_text(encoding="utf-8"))


def test_real_summary_passes_but_cannot_establish_defense_effect(results):
    report = audit.audit_evaluation(results)
    assert report["valid"]
    assert not report["baseline_attack_observed"]
    assert sum(p["model_calls"] for p in report["protocols"].values()) == 480


@pytest.mark.parametrize("field,value", [("task_success_rate", 0.1), ("task_success_rate", float("nan")),
                                        ("valid_runs", -1), ("utility_successes", 21), ("attacked", 0)])
def test_invalid_experiment_values_are_blocked(results, field, value):
    results["id"]["groups"][0][field] = value
    with pytest.raises(ValueError):
        audit.audit_evaluation(results)


def test_duplicate_conditions_and_mismatched_corpus_are_blocked(results):
    altered = copy.deepcopy(results)
    altered["id"]["groups"][1] = altered["id"]["groups"][0]
    with pytest.raises(ValueError):
        audit.audit_evaluation(altered)
    results["index"]["config"]["corpus_sha256"] = "different"
    with pytest.raises(ValueError):
        audit.audit_evaluation(results)


def add(manager, identifier="CIT-1-01"):
    trace = SimpleNamespace(query="agent security", summary="verified metadata", timestamp="2026-11-18")
    return manager.add_citation(identifier, "web_search", trace, "", tool_metadata={"results": [
        {"title": "Paper", "url": "https://arxiv.org/abs/2410.07283v1"}]})


def test_citations_work_without_full_runtime_and_restore_counters(tmp_path):
    manager = citation.CitationManager("paper", tmp_path)
    assert add(manager, "CIT-1-07")
    restored = citation.CitationManager("paper", tmp_path)
    assert restored.generate_research_citation_id("block_1") == "CIT-1-08"
    assert restored.validate_citation_references("[[CIT-1-07]]")["is_valid"]
    assert not restored.validate_citation_references("[[CIT-broken]]")["is_valid"]


def test_corrupt_archive_is_preserved(tmp_path):
    path = tmp_path / "citations.json"
    path.write_text('{"citations":', encoding="utf-8")
    with pytest.raises(ValueError, match="preserve"):
        citation.CitationManager("paper", tmp_path)
    assert path.read_text() == '{"citations":'


def test_failed_save_keeps_old_file_and_rolls_back_memory(tmp_path, monkeypatch):
    manager = citation.CitationManager("paper", tmp_path)
    assert add(manager)
    previous = manager.citations_file.read_bytes()
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(citation.os, "replace", fail)
    assert not add(manager, "CIT-1-02")
    assert not manager.citation_exists("CIT-1-02")
    assert manager.citations_file.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


def test_archive_cannot_be_reused_for_different_research(tmp_path):
    assert add(citation.CitationManager("paper", tmp_path))
    with pytest.raises(ValueError):
        citation.CitationManager("other", tmp_path)
