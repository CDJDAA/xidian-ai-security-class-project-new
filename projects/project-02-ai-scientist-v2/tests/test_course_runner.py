"""Exercise credential gating and real process timeout without model calls."""
import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from course_tools import run_course


class CourseRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env_file = Path(self.directory.name) / "empty.env"
        self.env_file.write_text("COURSE_MODEL=deepseek-flash\n", encoding="utf-8")
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("No network in course runner tests"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_offline_preflight_preserves_model_and_reports_missing_key(self):
        captured = io.StringIO()
        with patch.object(sys, "argv", ["run_course.py", "preflight", "--env-file", str(self.env_file)]), contextlib.redirect_stdout(captured):
            self.assertEqual(run_course.main(), 0)
        report = json.loads(captured.getvalue())
        self.assertEqual(report["model"], "deepseek-flash")
        self.assertEqual(report["idea_count"], 3)
        self.assertFalse(report["api_key_present"])
        self.assertEqual(report["api_requests_sent"], 0)

    def test_ideation_requires_credentials_before_starting_child(self):
        with patch.object(sys, "argv", ["run_course.py", "ideate", "--env-file", str(self.env_file)]), patch.object(run_course.subprocess, "Popen") as start:
            with self.assertRaisesRegex(SystemExit, "No API key configured"):
                run_course.main()
            start.assert_not_called()

    def test_local_literature_generation_validates_output_and_marks_no_external_search(self):
        run_dir = Path(self.directory.name)
        (run_dir / "workshop.md").write_text("Local paper reading only.", encoding="utf-8")
        candidate = {field: "test" for field in ("Name", "Title", "Short Hypothesis", "Related Work", "Abstract", "Experiments", "Risk Factors and Limitations")}
        candidate["Name"] = "local_course_check"
        response = SimpleNamespace(
            model="deepseek-flash", usage=SimpleNamespace(prompt_tokens=5, completion_tokens=10),
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"idea": candidate})))],
        )
        client = MagicMock()
        client.with_options.return_value.chat.completions.create.return_value = response
        with patch("ai_scientist.llm.create_client", return_value=(client, "deepseek-flash")):
            self.assertEqual(run_course.local_ideation_worker(run_dir, "deepseek-flash"), 0)
        self.assertEqual(json.loads((run_dir / "workshop.json").read_text())[0]["Name"], "local_course_check")
        provenance = json.loads((run_dir / "provenance.json").read_text())
        self.assertFalse(provenance["external_novelty_search"])
        self.assertEqual(provenance["model_requests_sent"], 1)

    def test_provider_error_does_not_echo_sensitive_message(self):
        captured = io.StringIO()
        with patch("ai_scientist.llm.create_client", side_effect=ValueError("invalid key sk-secret-test")), contextlib.redirect_stdout(captured):
            result = run_course.local_ideation_worker(Path(self.directory.name), "deepseek-flash")
        self.assertEqual(result, 1)
        self.assertNotIn("sk-secret-test", captured.getvalue())
        self.assertEqual(json.loads(captured.getvalue())["error_type"], "ValueError")

    @unittest.skipUnless(os.name == "posix", "Process groups are validated in Linux/WSL")
    def test_wall_clock_timeout_stops_a_real_child(self):
        started = time.monotonic()
        result = run_course.bounded_run([sys.executable, "-c", "import time; time.sleep(30)"], 1)
        self.assertEqual(result, 124)
        self.assertLess(time.monotonic() - started, 8)


if __name__ == "__main__":
    unittest.main()
