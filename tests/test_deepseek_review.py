"""DeepSeek PR review 脚本回归测试。"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "deepseek_review.py"


def _load_module():
    """从脚本路径加载独立模块实例。"""
    spec = importlib.util.spec_from_file_location("deepseek_review", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": "LGTM"}}]}
        ).encode()


class DeepSeekReviewTest(unittest.TestCase):
    def test_defaults_target_deepseek_v4_pro(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            module = _load_module()

        self.assertEqual(module.BASE_URL, "https://api.deepseek.com/v1")
        self.assertEqual(module.MODEL, "deepseek-v4-pro")

    def test_request_uses_deepseek_model_and_bearer_key(self) -> None:
        module = _load_module()
        captured = {}

        def fake_urlopen(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse()

        with patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = module._call_deepseek("secret-value", "PR title", "diff body")

        request = captured["request"]
        payload = json.loads(request.data)
        self.assertEqual(result, "LGTM")
        self.assertEqual(request.full_url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-value")
        self.assertEqual(payload["model"], "deepseek-v4-pro")
        self.assertEqual(captured["timeout"], module.TIMEOUT_S)

    def test_missing_key_writes_non_blocking_failure(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            module.OUT_PATH = str(Path(tmpdir) / "review.md")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(SystemExit, "0"):
                    module.main()
            body = Path(module.OUT_PATH).read_text()

        self.assertIn("DeepSeek V4 Pro PR Review", body)
        self.assertIn("DEEPSEEK_API_KEY 未配置", body)
        self.assertNotIn("GLM-5.2", body)


if __name__ == "__main__":
    unittest.main()
