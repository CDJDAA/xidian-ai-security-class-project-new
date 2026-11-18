"""Run the four coursework modules as an auditable, CPU-only paper handoff.

This is not the full autonomous research, GPU experiment or tutoring platform.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

PROJECTS = Path(__file__).resolve().parents[3]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, PROJECTS / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--id", action="append", required=True)
    args = parser.parse_args()
    if not 1 <= len(args.id) <= 5:
        parser.error("Use one to five references")
    args.output.mkdir(parents=True, exist_ok=False)
    for folder in ("project-01-ai-researcher", "project-04-Intelligence Gathering"):
        sys.path.insert(0, str(PROJECTS / folder))
    from research_agent.arxiv_metadata import normalize_arxiv_id
    from pipeline.evidence_export import build_evidence_bundle

    search = load("paper_search", "project-01-ai-researcher/research_agent/inno/tools/inno_tools/paper_search.py")
    batch = load("arxiv_batch", "project-01-ai-researcher/coursework/arxiv_smoke.py")
    audit = load("paper_audit", "project-02-ai-scientist-v2/ai_scientist/evidence_audit.py")
    citations = load("paper_citations", "project-03-deeptutor/deeptutor/agents/research/utils/citation_manager.py")
    summary_file = Path(__file__).with_name("results_v2.json")
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    audit_result = audit.audit_evaluation(summary)
    save(args.output / "experiment-audit.json", audit_result)

    def checkpoint(index, result, reused, seconds):
        save(args.output / f"reference-{index + 1}.json", {
            "metadata": result, "reused": reused, "seconds": seconds})

    fetched = batch.lookup_references(args.id, search.get_arxiv_paper_meta, normalize_arxiv_id,
                                      on_result=checkpoint)
    if any(row[0] is None for row in fetched):
        raise SystemExit("Reference retrieval incomplete; successful checkpoints preserved")
    items, claims = [], []
    manager = citations.CitationManager("multi-agent-security-paper", args.output / "citations")
    markers = []
    for index, (paper, reused, seconds) in enumerate(fetched, 1):
        url = "https://arxiv.org/abs/" + paper["arxiv_id"]
        items.append({"title": paper["title"], "text": paper["abstract"], "source_url": url})
        quote = paper["abstract"].split(". ")[0].strip()[:900]
        claims.append({"source_index": index, "text": quote, "quote": quote})
        citation_id = manager.generate_research_citation_id("block_1")
        trace = SimpleNamespace(query=paper["arxiv_id"], summary="Version-checked arXiv metadata",
                                timestamp=datetime.now(timezone.utc).isoformat())
        if not manager.add_citation(citation_id, "paper_search", trace, "", tool_metadata={"papers": [
                {**paper, "url": url, "year": paper["published"].year}]}):
            raise RuntimeError("Citation was not persisted")
        markers.append(f"[[{citation_id}]]")
    bundle = build_evidence_bundle(items, {"claims": claims})
    if bundle["verification"]["accepted"] != len(items):
        raise RuntimeError("Evidence handoff verification failed")
    save(args.output / "evidence-bundle.json", bundle)
    validation = manager.validate_citation_references(" ".join(markers))
    save(args.output / "citation-check.json", validation)
    manifest = {"completed": validation["is_valid"], "references": len(items),
                "metadata_requests": sum(not row[1] for row in fetched), "model_calls_this_run": 0,
                "historical_evaluation_sha256": hashlib.sha256(summary_file.read_bytes()).hexdigest(),
                "execution_scope": {"01": "live metadata lookup and checkpointing",
                                    "02": "offline pre-writeup experiment audit",
                                    "03": "citation persistence and reference validation",
                                    "04": "program-bound extractive evidence export"},
                "full_autonomous_frameworks_executed": False}
    save(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
