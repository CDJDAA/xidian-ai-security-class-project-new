"""Explicit course configuration, offline preflight, and bounded opt-in runs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def local_ideation_worker(run_dir: Path, model: str) -> int:
    """Generate a plan from the supplied corpus; do not claim external novelty."""
    from ai_scientist.llm import create_client, deepseek_request_kwargs
    from check_environment import validate_idea_file
    try:
        client, actual_model = create_client(model)
        evidence = (run_dir / "workshop.md").read_text(encoding="utf-8")
        system = (
            "Return a JSON object with one key 'idea'. Its value must contain Name (lowercase underscores), "
            "Title, Short Hypothesis, Related Work, Abstract, Experiments (list of strings), "
            "and Risk Factors and Limitations (list of strings). Refine the recommended course study "
            "using only the supplied local paper-reading evidence. Preserve the frozen evaluation protocol "
            "and compute-matched baselines. Do not invent citations or experimental results, and explicitly "
            "state that external novelty search has not been completed. Write the proposal in Chinese."
        )
        response = client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=actual_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": evidence}],
            response_format={"type": "json_object"}, max_tokens=4096,
            **deepseek_request_kwargs(actual_model),
        )
        payload = json.loads(response.choices[0].message.content or "")
        candidate = payload.get("idea", payload)
        path = run_dir / "workshop.json"
        path.write_text(json.dumps([candidate], ensure_ascii=False, indent=2), encoding="utf-8")
        validate_idea_file(path)
        usage = response.usage
        provenance = {
            "requested_model": model, "returned_model": response.model,
            "literature_mode": "supplied_local_pdf_reading", "external_novelty_search": False,
            "model_requests_sent": 1,
            "usage": None if usage is None else {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens},
        }
        (run_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Generated and schema-validated one local-literature candidate: {path}")
        return 0
    except Exception as exc:
        # Invalid-key provider messages can echo credentials; expose metadata only.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "http_status": getattr(exc, "status_code", None)}))
        return 1


def bounded_run(command: list[str], seconds: int) -> int:
    if os.name != "posix":
        raise SystemExit("Run this course wrapper inside Linux/WSL2.")
    child = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    try:
        return child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        print(f"Course wall-clock limit reached ({seconds}s); stopping the process group.")
        try:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        return 124
    except KeyboardInterrupt:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        return 130


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "ideate", "experiment", "worker", "local-ideation-worker"), nargs="?", default="preflight")
    parser.add_argument("--env-file", type=Path, default=Path.home() / ".config/ai-scientist-v2/course.env")
    parser.add_argument("--ideas", type=Path, default=ROOT / "ai_scientist/ideas/course_transfer_budget.json")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/course_smoke.yaml")
    parser.add_argument("--idea-idx", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--worker-config", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--literature", choices=("local", "semantic-scholar"), default="local")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    from dotenv import load_dotenv
    import yaml
    from check_environment import validate_idea_file

    load_dotenv(args.env_file, override=False)
    model = os.environ.get("COURSE_MODEL", "deepseek-flash")
    os.environ.setdefault("DEEPSEEK_BASE_URL", os.environ.get("OPENAI_BASE_URL") or "https://api.deepseek.com/v1")
    os.environ.setdefault("OPENAI_BASE_URL", os.environ["DEEPSEEK_BASE_URL"])
    os.environ.setdefault("WANDB_MODE", "disabled")
    os.environ.setdefault("MPLBACKEND", "Agg")

    if args.mode == "local-ideation-worker":
        if args.run_dir is None:
            parser.error("local-ideation-worker requires --run-dir")
        return local_ideation_worker(args.run_dir, model)

    if args.mode == "worker":
        if args.worker_config is None:
            parser.error("worker requires --worker-config")
        from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import perform_experiments_bfts
        os.environ["AI_SCIENTIST_ROOT"] = str(ROOT)
        perform_experiments_bfts(str(args.worker_config))
        return 0

    validate_idea_file(args.ideas)
    ideas = json.loads(args.ideas.read_text(encoding="utf-8"))
    if not 0 <= args.idea_idx < len(ideas):
        parser.error("--idea-idx is out of range")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    for role in ("code", "feedback", "vlm_feedback", "summary", "select_node"):
        config["agent"][role]["model"] = model
    config["report"]["model"] = model
    has_key = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if args.mode == "preflight":
        print(json.dumps({
            "mode": "offline_preflight", "model": model,
            "config": str(args.config.resolve()), "idea_count": len(ideas),
            "selected_idea": ideas[args.idea_idx]["Name"],
            "api_key_present": has_key, "api_requests_sent": 0,
            "workers": config["agent"]["num_workers"],
            "stage_limits": config["agent"]["stages"],
            "note": "No model availability or research result is claimed by preflight."
        }, ensure_ascii=False, indent=2))
        return 0
    if not has_key:
        raise SystemExit(f"No API key configured. Fill {args.env_file} locally; do not put it in the repository.")

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    run_dir = ROOT / "experiments" / f"course_{args.mode}_{stamp}"
    run_dir.mkdir(parents=True)
    if args.mode == "ideate":
        topic = run_dir / "workshop.md"
        topic_text = (ROOT / "ai_scientist/ideas/course_transfer_budget.md").read_text(encoding="utf-8")
        evidence = (ROOT / "docs/research/transfer-attack-budget.md").read_text(encoding="utf-8")
        topic.write_text(topic_text + "\n\n## Local paper reading and frozen course protocol\n\n" + evidence, encoding="utf-8")
        if args.literature == "local":
            command = [sys.executable, str(Path(__file__).resolve()), "local-ideation-worker",
                       "--env-file", str(args.env_file), "--run-dir", str(run_dir)]
        else:
            command = [sys.executable, str(ROOT / "ai_scientist/perform_ideation_temp_free.py"),
                       "--workshop-file", str(topic), "--model", model,
                       "--max-num-generations", "1", "--num-reflections", "2"]
    else:
        # Call the experiment API with this exact config. The upstream launcher
        # has no --config option and would otherwise read the default YAML.
        idea_path = run_dir / "idea.json"
        idea_path.write_text(json.dumps(ideas[args.idea_idx], ensure_ascii=False, indent=2), encoding="utf-8")
        config.update({"desc_file": str(idea_path), "workspace_dir": str(run_dir),
                       "log_dir": str(run_dir / "logs"), "data_dir": str(run_dir / "data")})
        (run_dir / "data").mkdir()
        config_path = run_dir / "bfts_config.yaml"
        config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print("This mode executes model-generated code and uses the model API. Use a controlled experiment environment.")
        command = [sys.executable, str(Path(__file__).resolve()), "worker", "--env-file", str(args.env_file),
                   "--worker-config", str(config_path)]
    print(f"Run artifacts: {run_dir}", flush=True)
    result = bounded_run(command, args.timeout)
    if args.mode == "ideate" and result == 0:
        generated = run_dir / "workshop.json"
        if not generated.exists() or not json.loads(generated.read_text(encoding="utf-8")):
            raise SystemExit("Ideation did not produce nonempty valid ideas; inspect the run log.")
        validate_idea_file(generated)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
