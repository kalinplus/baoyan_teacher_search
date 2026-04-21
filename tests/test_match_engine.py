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

from llm.match_engine import run_matching


class TestRunMatching(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_matches_teachers_and_outputs_recommendations(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "llm_enriched.json"
            resume_path = Path(tmpdir) / "resume.txt"
            interests_path = Path(tmpdir) / "interests.txt"
            output_path = Path(tmpdir) / "recommendations.json"

            input_data = {
                "school": "清华大学",
                "college": "计算机系",
                "teacher_profiles": [
                    {
                        "name": "甲",
                        "llm_basic": {"research_keywords": ["NLP", "深度学习"]},
                    },
                    {
                        "name": "乙",
                        "llm_basic": {"research_keywords": ["计算机视觉"]},
                    },
                ],
            }
            input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")
            resume_path.write_text("我是计算机系本科生，对NLP感兴趣", encoding="utf-8")
            interests_path.write_text("自然语言处理、大语言模型、深度学习", encoding="utf-8")

            def mock_extract(system_prompt, user_text):
                if "甲" in user_text:
                    return {"match_score": 85, "match_reasons": ["研究方向高度匹配"], "risk_flags": []}
                return {"match_score": 40, "match_reasons": ["方向不太相关"], "risk_flags": ["方向不匹配"]}

            with patch("llm.match_engine.LLMClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.extract_structured.side_effect = mock_extract

                stats = run_matching(
                    str(input_path),
                    str(resume_path),
                    str(interests_path),
                    str(output_path),
                )

            self.assertEqual(stats["total"], 2)

            output = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(output["recommendations"]), 2)

            rec_jia = output["recommendations"][0]
            self.assertEqual(rec_jia["teacher"], "甲")
            self.assertEqual(rec_jia["match_score"], 85)

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_failure_per_teacher_does_not_block_batch(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "llm_enriched.json"
            resume_path = Path(tmpdir) / "resume.txt"
            interests_path = Path(tmpdir) / "interests.txt"
            output_path = Path(tmpdir) / "recommendations.json"

            input_data = {
                "school": "清华大学",
                "college": "计算机系",
                "teacher_profiles": [
                    {"name": "甲", "llm_basic": {"research_keywords": ["NLP"]}},
                ],
            }
            input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")
            resume_path.write_text("简历", encoding="utf-8")
            interests_path.write_text("NLP", encoding="utf-8")

            with patch("llm.match_engine.LLMClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.extract_structured.side_effect = RuntimeError("API error")

                stats = run_matching(
                    str(input_path),
                    str(resume_path),
                    str(interests_path),
                    str(output_path),
                )

            self.assertEqual(stats["total"], 1)
            self.assertEqual(stats["failed"], 1)

            output = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(output["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
