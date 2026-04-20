import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from batch_closed_loop import run_batch_closed_loop, save_final_recommendations


class TestBatchClosedLoop(unittest.TestCase):
    def _write_input_files(self, root: Path) -> None:
        target_dir = root / "清华大学" / "计算机科学与技术系"
        target_dir.mkdir(parents=True, exist_ok=True)

        teachers_payload = {
            "school": "清华大学",
            "college": "计算机科学与技术系",
            "teacher_profiles": [
                {
                    "name": "甲",
                    "profile_url": "https://example.com/a",
                    "email": "a@example.com",
                    "interests": ["机器学习"],
                    "title": "教授",
                    "source_url": "https://example.com/source",
                },
                {
                    "name": "乙",
                    "profile_url": "https://example.com/b",
                    "email": "b@example.com",
                    "interests": ["计算机视觉"],
                    "title": "副教授",
                    "source_url": "https://example.com/source",
                },
            ],
        }
        prescreen_payload = {
            "school": "清华大学",
            "college": "计算机科学与技术系",
            "top_candidates": [
                {"name": "甲", "score": 95, "tier": "A", "reasons": ["has_profile_url"]},
                {"name": "乙", "score": 82, "tier": "B", "reasons": ["has_email"]},
            ],
        }

        (target_dir / "teachers.json").write_text(
            json.dumps(teachers_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (target_dir / "prescreen.json").write_text(
            json.dumps(prescreen_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_run_batch_closed_loop_success(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            out_dir = Path(temp_dir) / "out"
            self._write_input_files(pool_dir)

            resolved_results = [
                {
                    "teacher": "甲",
                    "status": "resolved",
                    "skip_reason": None,
                    "author_id": "AAA111",
                    "author_id_source": "google_search",
                    "matched_school": "清华大学",
                    "matched_teacher": "甲",
                    "error": None,
                },
                {
                    "teacher": "乙",
                    "status": "resolved",
                    "skip_reason": None,
                    "author_id": "BBB222",
                    "author_id_source": "google_search",
                    "matched_school": "清华大学",
                    "matched_teacher": "乙",
                    "error": None,
                },
            ]
            scholar_results = [
                {
                    "teacher": "甲",
                    "author_id": "AAA111",
                    "author_id_source": "google_search",
                    "status": "success",
                    "error": None,
                    "scholar_metrics": {
                        "name": "A",
                        "affiliations": "THU",
                        "email": "a@tsinghua.edu.cn",
                        "interests": ["ML"],
                        "citations_all": 100,
                        "citations_last_1y": 10,
                        "citations_last_3y": 30,
                        "citations_last_5y": 40,
                        "publications_total": 50,
                        "publications_last_1y": 3,
                        "publications_last_3y": 8,
                        "publications_last_5y": 12,
                        "publications_truncated": False,
                        "h_index_all": 20,
                        "i10_index_all": 30,
                    },
                },
                {
                    "teacher": "乙",
                    "author_id": "BBB222",
                    "author_id_source": "google_search",
                    "status": "success",
                    "error": None,
                    "scholar_metrics": {
                        "name": "B",
                        "affiliations": "THU",
                        "email": "b@tsinghua.edu.cn",
                        "interests": ["CV"],
                        "citations_all": 80,
                        "citations_last_1y": 7,
                        "citations_last_3y": 20,
                        "citations_last_5y": 30,
                        "publications_total": 40,
                        "publications_last_1y": 2,
                        "publications_last_3y": 7,
                        "publications_last_5y": 10,
                        "publications_truncated": True,
                        "h_index_all": 15,
                        "i10_index_all": 22,
                    },
                },
            ]

            with patch("batch_closed_loop.resolve_teacher_author_id", side_effect=resolved_results):
                with patch(
                    "batch_closed_loop.run_scholar_batch",
                    side_effect=[[scholar_results[0]], [scholar_results[1]]],
                ):
                    payload = run_batch_closed_loop(
                        school="清华大学",
                        college="计算机科学与技术系",
                        pool_dir=pool_dir,
                        out_dir=out_dir,
                        timeout=60,
                    )

            self.assertEqual(payload["total_candidates"], 2)
            self.assertEqual(payload["resolved_candidates"], 2)
            self.assertEqual(payload["failed_candidates"], 0)
            self.assertEqual(len(payload["recommendations"]), 2)
            self.assertEqual(payload["recommendations"][0]["teacher"], "甲")

            output_path = save_final_recommendations(out_dir=out_dir, payload=payload)
            saved_payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_payload["school"], "清华大学")
            self.assertEqual(saved_payload["college"], "计算机科学与技术系")

    def test_run_batch_closed_loop_records_skip_reason(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            out_dir = Path(temp_dir) / "out"
            self._write_input_files(pool_dir)

            side_effect_results = [
                {
                    "teacher": "甲",
                    "status": "skip",
                    "skip_reason": "author_id_conflict_existing_teacher",
                    "author_id": None,
                    "author_id_source": None,
                    "matched_school": "清华大学",
                    "matched_teacher": "甲",
                    "error": "skip_reason=author_id_conflict_existing_teacher",
                },
                {
                    "teacher": "乙",
                    "status": "resolved",
                    "skip_reason": None,
                    "author_id": "BBB222",
                    "author_id_source": "google_search",
                    "matched_school": "清华大学",
                    "matched_teacher": "乙",
                    "error": None,
                },
            ]
            scholar_results = [
                {
                    "teacher": "乙",
                    "author_id": "BBB222",
                    "author_id_source": "google_search",
                    "status": "success",
                    "error": None,
                    "scholar_metrics": {
                        "name": "B",
                        "affiliations": "THU",
                        "email": "b@tsinghua.edu.cn",
                        "interests": ["CV"],
                        "citations_all": 80,
                        "citations_last_1y": 7,
                        "citations_last_3y": 20,
                        "citations_last_5y": 30,
                        "publications_total": 40,
                        "publications_last_1y": 2,
                        "publications_last_3y": 7,
                        "publications_last_5y": 10,
                        "publications_truncated": False,
                        "h_index_all": 15,
                        "i10_index_all": 22,
                    },
                }
            ]

            with patch("batch_closed_loop.resolve_teacher_author_id", side_effect=side_effect_results):
                with patch("batch_closed_loop.run_scholar_batch", return_value=scholar_results):
                    payload = run_batch_closed_loop(
                        school="清华大学",
                        college="计算机科学与技术系",
                        pool_dir=pool_dir,
                        out_dir=out_dir,
                        timeout=60,
                    )

            self.assertEqual(payload["total_candidates"], 2)
            self.assertEqual(payload["resolved_candidates"], 1)
            self.assertEqual(payload["failed_candidates"], 1)
            self.assertEqual(payload["failed_candidate_details"][0]["teacher"], "甲")
            self.assertEqual(
                payload["failed_candidate_details"][0]["skip_reason"],
                "author_id_conflict_existing_teacher",
            )

    def test_run_batch_closed_loop_continue_on_unexpected_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            out_dir = Path(temp_dir) / "out"
            self._write_input_files(pool_dir)

            with patch("batch_closed_loop.resolve_teacher_author_id", side_effect=RuntimeError("network_failed")):
                payload = run_batch_closed_loop(
                    school="清华大学",
                    college="计算机科学与技术系",
                    pool_dir=pool_dir,
                    out_dir=out_dir,
                    timeout=60,
                )

            self.assertEqual(payload["total_candidates"], 2)
            self.assertEqual(payload["resolved_candidates"], 0)
            self.assertEqual(payload["failed_candidates"], 2)
            self.assertEqual(len(payload["recommendations"]), 0)
            self.assertEqual(payload["failed_candidate_details"][0]["stage"], "author_disambiguation")
            self.assertEqual(payload["failed_candidate_details"][0]["error"], "network_failed")

    def test_run_batch_closed_loop_fail_fast_on_input_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            out_dir = Path(temp_dir) / "out"
            self._write_input_files(pool_dir)

            prescreen_path = pool_dir / "清华大学" / "计算机科学与技术系" / "prescreen.json"
            prescreen_payload = json.loads(prescreen_path.read_text(encoding="utf-8"))
            prescreen_payload["top_candidates"][0]["name"] = "不存在的老师"
            prescreen_path.write_text(json.dumps(prescreen_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                run_batch_closed_loop(
                    school="清华大学",
                    college="计算机科学与技术系",
                    pool_dir=pool_dir,
                    out_dir=out_dir,
                    timeout=60,
                )


if __name__ == "__main__":
    unittest.main()
