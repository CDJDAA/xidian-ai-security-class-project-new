"""Offline deployment checks using the course's shared idea schema.

This validates local files and executes only the fixed, reviewed GPU code below.
It never creates a model client or sends model/API requests.
"""
import argparse
import importlib.metadata
import json
import multiprocessing
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The seven fields documented by perform_ideation_temp_free.py's FinalizeIdea
# tool, including all five fields checked by AgentManager and the launcher Name.
# course_runner imports this same object/function rather than duplicating it.
IDEA_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "required": ["Name", "Title", "Short Hypothesis", "Related Work", "Abstract", "Experiments", "Risk Factors and Limitations"],
        "properties": {
            "Name": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
            **{key: {"type": "string", "minLength": 1} for key in ("Title", "Short Hypothesis", "Related Work", "Abstract")},
            **{key: {"oneOf": [{"type": "string", "minLength": 1}, {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}]} for key in ("Experiments", "Risk Factors and Limitations")},
        },
        "additionalProperties": True,
    },
}

REVIEWED_GPU_PROGRAM = '''
import torch
assert torch.cuda.is_available(), "CUDA unavailable in Interpreter child"
torch.manual_seed(42)
model = torch.nn.Linear(4, 2, device="cuda")
inputs = torch.ones((2, 4), device="cuda")
loss = model(inputs).square().mean()
loss.backward()
assert all(torch.isfinite(p.grad).all().item() for p in model.parameters())
torch.cuda.synchronize()
print("COURSE_REVIEWED_INTERPRETER_GPU_OK")
'''


def validate_idea_file(path):
    import jsonschema
    ideas = json.loads(Path(path).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(IDEA_SCHEMA)
    jsonschema.Draft7Validator(IDEA_SCHEMA).validate(ideas)
    return ideas


def gpu_and_interpreter_checks():
    import torch
    from ai_scientist.treesearch.interpreter import Interpreter

    result = {"available": torch.cuda.is_available(), "torch_cuda": torch.version.cuda}
    if not result["available"]:
        raise RuntimeError("CUDA is not available to this project environment.")
    result["device"] = torch.cuda.get_device_name(0)
    result["capability"] = list(torch.cuda.get_device_capability(0))
    result["wheel_architectures"] = torch.cuda.get_arch_list()
    model = torch.nn.Linear(4, 2, device="cuda")
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    inputs = torch.ones((2, 4), device="cuda")
    loss = model(inputs).square().mean()
    loss.backward()
    assert all(torch.isfinite(p.grad).all().item() for p in model.parameters())
    optimizer.step()
    torch.cuda.synchronize()
    result["tensor_gradient_step"] = "passed"
    del model, optimizer, inputs, loss
    torch.cuda.empty_cache()

    # Spawn avoids forking a process after this parent initialized CUDA.
    with tempfile.TemporaryDirectory(prefix="ai-scientist-course-check-") as directory:
        interpreter = Interpreter(directory, timeout=30)
        try:
            execution = interpreter.run(REVIEWED_GPU_PROGRAM)
            if execution.exc_type is not None:
                raise RuntimeError(f"Reviewed Interpreter GPU code failed: {execution.exc_type}")
            if not any("COURSE_REVIEWED_INTERPRETER_GPU_OK" in item for item in execution.term_out):
                raise RuntimeError("Interpreter did not return its successful GPU marker.")
            result["reviewed_interpreter_gpu"] = "passed"
            result["interpreter_seconds"] = round(execution.exec_time, 3)
        finally:
            interpreter.cleanup_session()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ideas", type=Path, required=True, help="Course idea JSON to validate with the shared schema.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    multiprocessing.set_start_method("spawn", force=True)
    report = {
        "status": "failed", "python": platform.python_version(), "platform": platform.platform(),
        "model_requests_sent": 0, "versions": {},
        "credential_variable_present": any(name in os.environ for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY")),
        "optional_paper_tools": {name: bool(shutil.which(name)) for name in ("pdfinfo", "pdftoppm", "chktex", "pdflatex")},
    }
    try:
        for name in ("torch", "torchvision", "openai", "anthropic", "numpy", "transformers", "jsonschema"):
            report["versions"][name] = importlib.metadata.version(name)
        ideas = validate_idea_file(args.ideas)
        report["idea_schema"] = {"status": "passed", "count": len(ideas), "names": [idea["Name"] for idea in ideas]}
        report["gpu"] = gpu_and_interpreter_checks()
        report["status"] = "passed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
