"""Offline SDK stubs: no model requests, credentials, or paid API use."""
import io
import json
import os
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_scientist import llm, vlm
from ai_scientist.treesearch import backend
from ai_scientist.treesearch.backend import backend_openai
from course_tools.check_environment import validate_idea_file


def sdk_response(answer="ok", *, tool_name=None):
    tools = None
    if tool_name:
        tools = [SimpleNamespace(function=SimpleNamespace(name=tool_name, arguments='{"score": 1}'))]
    return SimpleNamespace(
        model="deepseek-flash", created=1, system_fingerprint=None,
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, completion_tokens_details=None),
        choices=[SimpleNamespace(message=SimpleNamespace(content=answer, tool_calls=tools))],
    )


class CourseModelCompatibilityTests(unittest.TestCase):
    def setUp(self):
        # Dummy test values only. Any unexpected networking fails this test suite.
        self.env = patch.dict(os.environ, {"DEEPSEEK_API_KEY": "dummy-test-key"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.client = MagicMock()
        self.client.chat.completions.create.return_value = sdk_response()

    def assert_course_request(self, request, model="deepseek-flash"):
        self.assertEqual(request["model"], model)
        self.assertNotIn("seed", request)
        self.assertNotIn("n", request)
        if model != "deepseek-chat":
            self.assertEqual(request["extra_body"], {"thinking": {"type": "disabled"}})

    def test_both_client_dispatchers_preserve_exact_deepseek_ids(self):
        for model in ("deepseek-chat", "deepseek-flash", "deepseek-v4-flash", "deepseek-v4-pro"):
            with self.subTest(model=model), patch.object(llm.openai, "OpenAI", return_value=self.client) as ctor:
                client, actual_model = llm.create_client(model)
                self.assertIs(client, self.client)
                self.assertEqual(actual_model, model)
                self.assertEqual(ctor.call_args.kwargs["base_url"], "https://api.deepseek.com/v1")
                self.assertEqual(ctor.call_args.kwargs["api_key"], "dummy-test-key")
                self.assertIs(backend.get_ai_client(model), self.client)

    def test_deepseek_credentials_and_url_take_priority(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "other-dummy", "OPENAI_BASE_URL": "https://other.invalid/v1", "DEEPSEEK_BASE_URL": "https://chosen.invalid/v1"}):
            kwargs = llm.deepseek_client_kwargs()
            self.assertEqual(kwargs["api_key"], "dummy-test-key")
            self.assertEqual(kwargs["base_url"], "https://chosen.invalid/v1")

    def test_openai_environment_fallback(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fallback-dummy", "OPENAI_BASE_URL": "https://fallback.invalid/v1"}, clear=True):
            kwargs = llm.deepseek_client_kwargs(max_retries=0)
            self.assertEqual(kwargs["api_key"], "fallback-dummy")
            self.assertEqual(kwargs["base_url"], "https://fallback.invalid/v1")
            self.assertEqual(kwargs["max_retries"], 0)

    def test_missing_credentials_do_not_construct_sdk_client(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(llm.openai, "OpenAI") as ctor:
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
                llm.create_client("deepseek-flash")
            ctor.assert_not_called()

    def test_single_text_response_preserves_history(self):
        previous = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "reply"}]
        answer, history = llm.get_response_from_llm("new", self.client, "deepseek-flash", system_message="system", msg_history=previous)
        self.assertEqual(answer, "ok")
        self.assertEqual(len(previous), 2)
        self.assertEqual(history[-1], {"role": "assistant", "content": "ok"})
        self.assert_course_request(self.client.chat.completions.create.call_args.kwargs)

    def test_legacy_chat_is_exact_and_has_no_forced_mode_alias(self):
        llm.get_response_from_llm("question", self.client, "deepseek-chat", system_message="system")
        request = self.client.chat.completions.create.call_args.kwargs
        self.assert_course_request(request, "deepseek-chat")
        self.assertNotIn("extra_body", request)

    def test_batch_text_uses_independent_single_requests(self):
        answers, histories = llm.get_batch_responses_from_llm("question", self.client, "deepseek-flash", system_message="system", n_responses=2)
        self.assertEqual(answers, ["ok", "ok"])
        self.assertEqual(len(histories), 2)
        self.assertEqual(self.client.chat.completions.create.call_count, 2)
        for call in self.client.chat.completions.create.call_args_list:
            self.assert_course_request(call.kwargs)

    def test_existing_gpt_batch_still_returns_a_tuple(self):
        self.client.chat.completions.create.return_value.choices *= 2
        answers, histories = llm.get_batch_responses_from_llm("question", self.client, "gpt-4o", system_message="system", n_responses=2)
        self.assertEqual(answers, ["ok", "ok"])
        self.assertEqual(len(histories), 2)

    def test_tree_search_tool_call_schema_and_non_thinking_mode(self):
        spec = backend.FunctionSpec(name="evaluate", description="test", json_schema={"type": "object", "properties": {"score": {"type": "integer"}}, "required": ["score"]})
        self.client.chat.completions.create.return_value = sdk_response(tool_name="evaluate")
        with patch.object(backend_openai, "get_ai_client", return_value=self.client), redirect_stdout(io.StringIO()):
            output = backend.query({"Instruction": "test"}, "result", "deepseek-flash", max_tokens=512, func_spec=spec, seed=0, n=1)
        self.assertEqual(output, {"score": 1})
        request = self.client.chat.completions.create.call_args.kwargs
        self.assert_course_request(request)
        self.assertEqual(request["tool_choice"], {"type": "function", "function": {"name": "evaluate"}})
        self.assertEqual(request["tools"][0]["function"]["parameters"], spec.json_schema)

    def test_tree_search_preserves_flash_multimodal_blocks(self):
        content = [{"type": "text", "text": "read the chart"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]
        with patch.object(backend_openai, "get_ai_client", return_value=self.client):
            self.assertEqual(backend.query("system", content, "deepseek-flash"), "ok")
        request = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["messages"][-1]["content"], content)
        self.assert_course_request(request)

    def test_tree_search_default_token_limit_and_explicit_smaller_limit(self):
        for supplied, expected in ((None, 4096), (128, 128)):
            with self.subTest(max_tokens=supplied), patch.object(backend_openai, "get_ai_client", return_value=self.client):
                backend.query("system", "question", "deepseek-flash", max_tokens=supplied)
            request = self.client.chat.completions.create.call_args.kwargs
            self.assertEqual(request["max_tokens"], expected)

    def test_text_only_models_reject_images_before_constructing_client(self):
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]
        for model in ("deepseek-chat", "deepseek-v4-pro"):
            with self.subTest(model=model), patch.object(backend_openai, "get_ai_client") as ctor:
                with self.assertRaisesRegex(ValueError, "vision model"):
                    backend.query("system", content, model)
                ctor.assert_not_called()

    def test_flash_vlm_client_and_image_request(self):
        with patch.object(vlm.openai, "OpenAI", return_value=self.client) as ctor:
            self.assertEqual(vlm.create_client("deepseek-flash"), (self.client, "deepseek-flash"))
            self.assertEqual(ctor.call_args.kwargs["base_url"], "https://api.deepseek.com/v1")
        with patch.object(vlm, "encode_image_to_base64", return_value="AA=="):
            answer, _ = vlm.get_response_from_vlm("chart", "not-read.png", self.client, "deepseek-flash", "system")
        self.assertEqual(answer, "ok")
        request = self.client.chat.completions.create.call_args.kwargs
        self.assert_course_request(request)
        self.assertEqual(request["messages"][-1]["content"][1]["type"], "image_url")

    def test_flash_batch_vlm_does_not_send_n_or_seed(self):
        with patch.object(vlm, "encode_image_to_base64", return_value="AA=="):
            answers, histories = vlm.get_batch_responses_from_vlm("chart", ["not-read.png"], self.client, "deepseek-flash", "system", n_responses=2)
        self.assertEqual(answers, ["ok", "ok"])
        self.assertEqual(len(histories), 2)
        for call in self.client.chat.completions.create.call_args_list:
            self.assert_course_request(call.kwargs)

    def test_vlm_does_not_claim_legacy_chat_or_pro_support(self):
        for model in ("deepseek-chat", "deepseek-v4-pro"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                vlm.create_client(model)

    def test_shared_idea_schema_accepts_upstream_fields(self):
        idea = {key: "test" for key in ("Name", "Title", "Short Hypothesis", "Related Work", "Abstract", "Experiments", "Risk Factors and Limitations")}
        idea["Name"] = "course_check"
        idea["Experiments"] = ["Measure accuracy on the fixed test set."]
        idea["Course Budget"] = {"gpu_count": 1}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ideas.json"
            path.write_text(json.dumps([idea]), encoding="utf-8")
            self.assertEqual(validate_idea_file(path), [idea])

    def test_shared_idea_schema_rejects_path_traversal_and_missing_fields(self):
        import jsonschema
        idea = {key: "test" for key in ("Name", "Title", "Short Hypothesis", "Related Work", "Abstract", "Experiments", "Risk Factors and Limitations")}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ideas.json"
            for change in ({"Name": "../outside"}, {"Experiments": []}):
                with self.subTest(change=change):
                    path.write_text(json.dumps([{**idea, **change}]), encoding="utf-8")
                    with self.assertRaises(jsonschema.ValidationError):
                        validate_idea_file(path)
            del idea["Title"]
            path.write_text(json.dumps([idea]), encoding="utf-8")
            with self.assertRaises(jsonschema.ValidationError):
                validate_idea_file(path)


if __name__ == "__main__":
    unittest.main()
