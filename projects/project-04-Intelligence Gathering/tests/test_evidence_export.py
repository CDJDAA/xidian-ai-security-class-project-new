from pipeline.evidence_export import build_evidence_bundle


def test_handoff_drops_unverified_model_prose_and_forged_claims():
    result = build_evidence_bundle([{"text": "This is source evidence.", "source_url": "https://example.org"}],
        {"topics": ["unverified claim"], "summary": "invented finding", "claims": [
            {"source_index": 1, "text": "This is source evidence.", "quote": "This is source evidence."},
            {"source_index": 1, "text": "invented finding", "quote": "invented finding"}]})
    assert result["verification"]["accepted"] == 1
    assert result["verification"]["rejected"] == 1
    assert "topics" not in result and "summary" not in result
    assert result["citations"][0]["source_id"] == result["sources"][0]["source_id"]
