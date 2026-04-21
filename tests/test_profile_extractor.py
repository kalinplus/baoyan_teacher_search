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

from llm.profile_extractor import extract_one_profile, run_extraction


class TestExtractOneProfile(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_basic_extraction_from_full_text(self):
        basic_result = {
            "title": "教授",
            "email": "zhang@tsinghua.edu.cn",
            "research_keywords": ["NLP", "深度学习"],
            "bio": "清华大学计算机系教授",
            "is_phd_supervisor": True,
            "is_master_supervisor": True,
            "homepage_url": None,
            "google_scholar_url": None,
            "github_url": None,
        }

        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_structured.return_value = basic_result

            teacher = {
                "name": "张三",
                "profile_url": "https://example.com/zhangsan",
                "homepage": {"full_text": "张三，教授，NLP与深度学习。博士生导师。邮箱zhang@tsinghua.edu.cn"},
            }

            result = extract_one_profile(mock_instance, teacher)

            self.assertEqual(result["name"], "张三")
            self.assertEqual(result["llm_basic"]["title"], "教授")
            self.assertEqual(result["llm_basic"]["email"], "zhang@tsinghua.edu.cn")
            self.assertIsNone(result.get("llm_extended"))

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_extended_extraction_when_homepage_url_exists(self):
        basic_result = {"title": "教授", "email": None, "research_keywords": [], "bio": None, "is_phd_supervisor": False, "is_master_supervisor": False, "homepage_url": "https://example.com", "google_scholar_url": None, "github_url": None}
        extended_result = {
            "research_summary": "研究NLP和深度学习",
            "recruiting_status": "active",
            "recruiting_targets": ["phd"],
            "recruiting_note": None,
            "recent_works": [],
            "lab_name": None,
            "awards": [],
            "conference_roles": [],
            "open_source_projects": [],
        }

        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_structured.side_effect = [basic_result, extended_result]

            with patch("llm.profile_extractor.fetch_homepage_text") as mock_fetch:
                mock_fetch.return_value = "个人主页内容"

                teacher = {
                    "name": "李四",
                    "profile_url": "https://example.com/lisi",
                    "homepage": {
                        "full_text": "李四，教授",
                        "personal_homepage": "https://personal.example.com",
                    },
                }

                result = extract_one_profile(mock_instance, teacher)
                self.assertEqual(result["llm_extended"]["recruiting_status"], "active")
                self.assertEqual(mock_instance.extract_structured.call_count, 2)

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_single_failure_does_not_block(self):
        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_structured.side_effect = RuntimeError("API error")

            teacher = {
                "name": "王五",
                "profile_url": "https://example.com/wangwu",
                "homepage": {"full_text": "王五信息"},
            }

            result = extract_one_profile(mock_instance, teacher)
            self.assertEqual(result["name"], "王五")
            self.assertIsNone(result.get("llm_basic"))
            self.assertIn("error", result)

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_skips_when_no_full_text(self):
        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            teacher = {
                "name": "赵六",
                "profile_url": "https://example.com/zhaoliu",
            }

            result = extract_one_profile(mock_instance, teacher)
            self.assertEqual(result["name"], "赵六")
            self.assertIsNone(result.get("llm_basic"))
            self.assertEqual(result.get("skip_reason"), "no_full_text")


class TestRunExtraction(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_batch_writes_incrementally(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "teachers.json"
            output_path = Path(tmpdir) / "llm_enriched.json"

            input_data = {
                "school": "清华大学",
                "college": "计算机系",
                "teacher_profiles": [
                    {"name": "甲", "profile_url": "https://a.com", "homepage": {"full_text": "甲信息"}},
                    {"name": "乙", "profile_url": "https://b.com", "homepage": {"full_text": "乙信息"}},
                ],
            }
            input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")

            with patch("llm.profile_extractor.LLMClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.extract_structured.return_value = {
                    "title": "教授", "email": None, "research_keywords": [],
                    "bio": None, "is_phd_supervisor": False, "is_master_supervisor": False,
                    "homepage_url": None, "google_scholar_url": None, "github_url": None,
                }

                run_extraction(str(input_path), str(output_path))

            output = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(output["teacher_profiles"]), 2)
            self.assertIsNotNone(output["teacher_profiles"][0]["llm_basic"])
            self.assertIsNotNone(output["teacher_profiles"][1]["llm_basic"])


if __name__ == "__main__":
    unittest.main()
