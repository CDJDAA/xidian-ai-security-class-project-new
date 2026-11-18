"""Run the original reference tool in isolation; no Docker, GPU or model key."""
import argparse
import importlib.util
import json
import platform
import shutil
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lookup_references(identifiers, lookup, normalize):
    """Deduplicate one batch by canonical ID, preserving order and revisions.

    Cache only successful results for this invocation; never retain a stale
    unversioned lookup across runs. Validate the whole batch before any I/O.
    """
    canonical = [normalize(value) for value in identifiers]
    cache = {}
    results = []
    last_request = None
    for identifier in canonical:
        reused = identifier in cache
        started = time.perf_counter()
        if reused:
            result = deepcopy(cache[identifier])
        else:
            if last_request is not None:
                time.sleep(max(0, 3 - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            result = lookup(identifier)
            if result is not None:
                cache[identifier] = deepcopy(result)
        results.append((result, reused, round(time.perf_counter() - started, 3)))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", action="append", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "coursework/local-runs/arxiv")
    args = parser.parse_args()
    if not 1 <= len(args.id) <= 3:
        parser.error("Choose between one and three references")
    if args.output.exists():
        parser.error("Output exists; use a new directory to preserve prior evidence")
    spec = importlib.util.spec_from_file_location("course01_paper_search", ROOT / "research_agent/inno/tools/inno_tools/paper_search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from research_agent.arxiv_metadata import normalize_arxiv_id

    try:
        identifiers = [normalize_arxiv_id(value) for value in args.id]
    except ValueError as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True)
    fetched = lookup_references(identifiers, module.get_arxiv_paper_meta, normalize_arxiv_id)
    results = []
    for index, (identifier, (result, reused, seconds)) in enumerate(zip(args.id, fetched)):
        if result:
            (args.output / f"paper-{index + 1}.json").write_text(json.dumps(result, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        results.append({"requested": identifier, "status": "retrieved" if result else "failed",
                        "returned_id": result["arxiv_id"] if result else None,
                        "title": result["title"] if result else None,
                        "response_sha256": result["provenance"]["response_sha256"] if result else None,
                        "reused_in_batch": reused, "seconds": seconds})
    summary = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
               "system": platform.system(), "module": "inno/tools/inno_tools/paper_search.py",
               "docker_cli_available": shutil.which("docker") is not None,
               "model_calls": 0, "metadata_requests": sum(not row["reused_in_batch"] for row in results),
               "full_research_workflow_executed": False, "results": results}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["status"] != "retrieved" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
