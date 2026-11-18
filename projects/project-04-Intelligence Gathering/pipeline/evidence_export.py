"""Portable source-bound evidence for downstream research and writing."""
from __future__ import annotations

from pipeline.grounding import source_record, verify_source_choices


def build_evidence_bundle(items: list[dict], candidate: dict) -> dict:
    sources = [source_record(item) for item in items]
    verified = verify_source_choices(candidate, sources)
    # Deliberately omit unverified model topics/summary from the handoff.
    return {"schema_version": 1, "sources": sources,
            "citations": verified["citations"], "verification": verified["verification"],
            "scope": "Exact quotations only; source truth and semantic relevance are not verified."}
