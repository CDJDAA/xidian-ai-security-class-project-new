"""Offline, reproducible CSV read benchmark; no crawler or model requests."""
import csv
import json
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

COURSE_ROOT = Path(__file__).resolve().parents[3] / "project-04-Intelligence Gathering"
sys.path.insert(0, str(COURSE_ROOT))
from pipeline.analysis_service import _read_rows  # noqa: E402


def measure(reader):
    timings, peaks = [], []
    for _ in range(3):
        tracemalloc.start()
        started = time.perf_counter()
        rows = reader()
        timings.append(time.perf_counter() - started)
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
    return rows, {"median_seconds": round(statistics.median(timings), 6),
                  "peak_python_bytes": max(peaks)}


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["title", "text"])
            writer.writerows((f"paper-{index}", "Synthetic research text " * 8) for index in range(100000))

        def baseline():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                return list(csv.DictReader(handle))[:500]

        old_rows, old = measure(baseline)
        new_rows, new = measure(lambda: _read_rows(path, 500))
        assert old_rows == new_rows
        print(json.dumps({"python": platform.python_version(), "system": platform.system(),
                          "fixture_rows": 100000, "requested_rows": 500, "repeats": 3,
                          "equal_output": True, "baseline": old, "bounded": new,
                          "network_calls": 0, "model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
