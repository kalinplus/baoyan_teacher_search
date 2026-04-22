import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv

from llm.llm_client import LLMClient


class TestLLMClientInit(unittest.TestCase):
    def test_raises_without_api_key(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(dotenv_path=env_path)
                with self.assertRaises(RuntimeError) as ctx:
                    LLMClient()
                self.assertIn("SILICONFLOW_API_KEY", str(ctx.exception))

    def test_init_with_api_key_from_env(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("SILICONFLOW_API_KEY=test-key", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(dotenv_path=env_path)
                client = LLMClient()
                self.assertEqual(client.model, "deepseek-ai/DeepSeek-V3.2")


class TestLLMClientExtract(unittest.TestCase):
    def test_extract_structured_returns_parsed_json(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("SILICONFLOW_API_KEY=test-key", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(dotenv_path=env_path)

                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps({"title": "教授", "email": "a@b.edu.cn"}, ensure_ascii=False)
                        )
                    )
                ]

                with patch("llm.llm_client.OpenAI") as MockOpenAI:
                    mock_client = MockOpenAI.return_value
                    mock_client.chat.completions.create.return_value = mock_response

                    client = LLMClient()
                    result = client.extract_structured(
                        system_prompt="Extract info",
                        user_text="张三，教授，邮箱 a@b.edu.cn",
                    )

                    self.assertEqual(result["title"], "教授")
                    self.assertEqual(result["email"], "a@b.edu.cn")

    def test_extract_structured_handles_malformed_json(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("SILICONFLOW_API_KEY=test-key", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(dotenv_path=env_path)

                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content="not json at all"))
                ]

                with patch("llm.llm_client.OpenAI") as MockOpenAI:
                    mock_client = MockOpenAI.return_value
                    mock_client.chat.completions.create.return_value = mock_response

                    client = LLMClient()
                    with self.assertRaises(ValueError) as ctx:
                        client.extract_structured("prompt", "text")
                    self.assertIn("JSON", str(ctx.exception))

    def test_extract_structured_retries_on_connection_error(self):
        import openai

        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("SILICONFLOW_API_KEY=test-key", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(dotenv_path=env_path)

                call_count = {"n": 0}
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content='{"title": "教授"}'))
                ]

                def side_effect(*args, **kwargs):
                    call_count["n"] += 1
                    if call_count["n"] < 3:
                        raise openai.APIConnectionError(message="connection failed", request=MagicMock())
                    return mock_response

                with patch("llm.llm_client.OpenAI") as MockOpenAI:
                    mock_client = MockOpenAI.return_value
                    mock_client.chat.completions.create.side_effect = side_effect

                    client = LLMClient()
                    result = client.extract_structured("prompt", "text")
                    self.assertEqual(result["title"], "教授")
                    self.assertEqual(call_count["n"], 3)

    def test_strip_markdown_json_from_response(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("SILICONFLOW_API_KEY=test-key", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                load_dotenv(dotenv_path=env_path)

                wrapped = '```json\n{"title": "教授", "email": "a@b.edu.cn"}\n```'
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content=wrapped))
                ]

                with patch("llm.llm_client.OpenAI") as MockOpenAI:
                    mock_client = MockOpenAI.return_value
                    mock_client.chat.completions.create.return_value = mock_response

                    client = LLMClient()
                    result = client.extract_structured("prompt", "text")
                    self.assertEqual(result["title"], "教授")
                    self.assertEqual(result["email"], "a@b.edu.cn")


if __name__ == "__main__":
    unittest.main()
