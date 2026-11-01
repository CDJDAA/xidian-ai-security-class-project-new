"""Run the original reference tool in isolation; no Docker, GPU or model key."""
import argparse
import importlib.util
import json
import platform
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", action="append", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "coursework/local-runs/arxiv")
    args = parser.parse_args()
    if not 1 <= len(args.id) <= 3:
        parser.error("Choose between one and three references")
    if args.output.exists():
        parser.error("Output exists; use a new directory to preserve prior evidence")
    args.output.mkdir(parents=True)
    spec = importlib.util.spec_from_file_location("course01_paper_search", ROOT / "research_agent/inno/tools/inno_tools/paper_search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = []
    for index, identifier in enumerate(args.id):
        if index:
            time.sleep(3)
        started = time.perf_counter()
        result = module.get_arxiv_paper_meta(identifier)
        if result:
            (args.output / f"paper-{index + 1}.json").write_text(json.dumps(result, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
        results.append({"requested": identifier, "status": "retrieved" if result else "failed",
                        "returned_id": result["arxiv_id"] if result else None,
                        "title": result["title"] if result else None,
                        "response_sha256": result["provenance"]["response_sha256"] if result else None,
                        "seconds": round(time.perf_counter() - started, 3)})
    summary = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
               "system": platform.system(), "module": "inno/tools/inno_tools/paper_search.py",
               "docker_cli_available": shutil.which("docker") is not None,
               "model_calls": 0, "full_research_workflow_executed": False, "results": results}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["status"] != "retrieved" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
