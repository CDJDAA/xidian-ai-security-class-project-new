import asyncio
import argparse
import json
import sys
from pathlib import Path

import pytest

from pipeline.grounding import source_record, verify_source_choices

RESEARCH = Path(__file__).resolve().parents[2] / "multi-agent-security-research"
sys.path.insert(0, str(RESEARCH))
from experiments.source_tracking.agents import ModelFailure, run_chain  # noqa: E402
from experiments.source_tracking.budget import CallBudget, RunLock  # noqa: E402
from experiments.source_tracking import evaluate as evaluation  # noqa: E402


def make_claim(index):
    return {"claims": [{"text": "可以核对的研究原文。", "quote": "可以核对的研究原文。", "source_index": index, "source_id": "src.forged"}]}


def test_choice_is_bound_by_program_not_model_hash():
    source = source_record({"text": "可以核对的研究原文。"})
    result = verify_source_choices(make_claim(1), [source])
    assert result["citations"][0]["source_id"] == source["source_id"]
    assert result["verification"]["source_binding"] == "program-index-v2"


@pytest.mark.parametrize("choice", [None, True, False, 0, -1, "1", 1.0, 2])
def test_missing_or_invalid_index_cannot_choose_a_source(choice):
    source = source_record({"text": "可以核对的研究原文。"})
    assert verify_source_choices(make_claim(choice), [source])["claims"] == []


def test_valid_index_cannot_borrow_another_sources_quote():
    sources = [source_record({"text": "可以核对的研究原文。"}), source_record({"text": "第二份资料没有相同的原文。"})]
    result = verify_source_choices(make_claim(2), sources)
    assert result["claims"] == []
    assert result["verification"]["reasons"][0]["reason"] == "quote_not_in_source"


def test_reserved_request_survives_restart_and_enforces_limit(tmp_path):
    path = tmp_path / "calls.ledger"
    budget = CallBudget(path, 2)
    assert budget.reserve()
    recovered = CallBudget(path, 2)
    assert recovered.used == 1
    assert recovered.reserve()
    assert not recovered.reserve()
    assert CallBudget(path, 2).used == 2


def test_corrupt_ledger_does_not_silently_reset_budget(tmp_path):
    path = tmp_path / "calls.ledger"
    path.write_bytes(b"reserved\ninterrupted")
    with pytest.raises(ValueError, match="Invalid call ledger"):
        CallBudget(path, 2)


def test_lock_prevents_double_writer_and_releases_after_failure(tmp_path):
    with pytest.raises(RuntimeError):
        with RunLock(tmp_path):
            with pytest.raises(ValueError, match="locked"):
                with RunLock(tmp_path):
                    pytest.fail("Another writer acquired the same output")
            raise RuntimeError("simulated failure")
    with RunLock(tmp_path):
        assert (tmp_path / ".running.lock").exists()


def test_budget_rejection_is_not_counted_as_a_network_call():
    class Client:
        async def complete(self, *args):
            raise ModelFailure("call_budget_exhausted", attempted=False)
    result = asyncio.run(run_chain(Client(), {"text": "正文"}, "提取", True))
    assert result["call_attempts"] == 0
    assert result["error"] == "call_budget_exhausted"


def test_index_is_preserved_across_all_three_handoffs():
    class Client:
        async def complete(self, system, payload):
            if payload["previous"]:
                assert payload["previous"]["claims"][0]["source_index"] == 1
            return make_claim(1), {"duration_seconds": 0}
    result = asyncio.run(run_chain(Client(), {"text": "可以核对的研究原文。"}, "提取", True, "index"))
    assert result["status"] == "completed"
    assert result["claims"][0]["source_index"] == 1
    assert len(result["trace"]) == result["call_attempts"] == 3


def test_resume_keeps_completed_results_and_spent_call_reservations(tmp_path, monkeypatch):
    class Client:
        def __init__(self, model, *, budget, **kwargs):
            self.budget = budget
            self.calls = budget.used
        async def complete(self, system, payload):
            assert self.budget.reserve()
            self.calls += 1
            return make_claim(1), {"duration_seconds": 0, "usage": {}}
        async def close(self): pass
    monkeypatch.setattr(evaluation, "ChatClient", Client)
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"case_id": "fixture", "title": "test", "text": "可以核对的研究原文。", "url": "https://example.org", "expected_claim": "可以核对的研究原文。"}) + "\n", encoding="utf-8")
    args = argparse.Namespace(corpus=corpus, output=tmp_path / "run", model="fixture", cases=1, offset=0,
                              repeats=1, max_calls=12, max_tokens=650, concurrency=1, resume=False, source_selection="index")
    first = asyncio.run(evaluation.evaluate(args))
    args.resume = True
    second = asyncio.run(evaluation.evaluate(args))
    assert first["total_runs"] == second["total_runs"] == 4
    assert second["reserved_call_attempts"] == second["total_call_attempts"] == 12
    assert not (args.output / ".running.lock").exists()
