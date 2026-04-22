import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from prescreen_closed_loop import run_prescreen_closed_loop, save_recommendations


class TestPrescreenClosedLoop(unittest.TestCase):
    def _write_input_files(self, root: Path) -> Path:
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
                    "homepage": {"research_fields": ["深度学习"]},
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
            "stats": {
                "total_profiles": 50,
                "scored_profiles": 50,
                "selected_profiles": 2,
                "skipped_profiles": 48,
            },
            "top_candidates": [
                {
                    "name": "甲",
                    "score": 95,
                    "tier": "A",
                    "rank": 1,
                    "reasons": ["has_profile_url", "has_email", "senior_title"],
                    "matched_keywords": ["深度学习"],
                },
                {
                    "name": "乙",
                    "score": 82,
                    "tier": "B",
                    "rank": 2,
                    "reasons": ["has_email", "title_signal"],
                    "matched_keywords": [],
                },
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
        return target_dir

    def test_run_prescreen_closed_loop_success(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            out_dir = Path(temp_dir) / "out"
            self._write_input_files(pool_dir)

            payload = run_prescreen_closed_loop(
                school="清华大学",
                college="计算机科学与技术系",
                pool_dir=pool_dir,
            )

        self.assertEqual(payload["school"], "清华大学")
        self.assertEqual(payload["college"], "计算机科学与技术系")
        self.assertEqual(payload["source"], "prescreen_only")
        self.assertEqual(payload["total_candidates"], 2)
        self.assertEqual(len(payload["recommendations"]), 2)

        rec_a = payload["recommendations"][0]
        self.assertEqual(rec_a["teacher"], "甲")
        self.assertEqual(rec_a["prescreen_score"], 95)
        self.assertEqual(rec_a["prescreen_tier"], "A")
        self.assertEqual(rec_a["profile"]["email"], "a@example.com")
        self.assertEqual(rec_a["profile"]["homepage"], {"research_fields": ["深度学习"]})
        self.assertIn("keywords=深度学习", rec_a["recommendation_reason"])
        self.assertEqual(rec_a["risk_flags"], [])

    def test_risk_flags_detect_missing_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            self._write_input_files(pool_dir)

            teachers_path = pool_dir / "清华大学" / "计算机科学与技术系" / "teachers.json"
            teachers = json.loads(teachers_path.read_text(encoding="utf-8"))
            teachers["teacher_profiles"][1]["email"] = None
            teachers["teacher_profiles"][1]["profile_url"] = None
            teachers["teacher_profiles"][1]["interests"] = []
            teachers_path.write_text(json.dumps(teachers, ensure_ascii=False, indent=2), encoding="utf-8")

            payload = run_prescreen_closed_loop(
                school="清华大学",
                college="计算机科学与技术系",
                pool_dir=pool_dir,
            )

        rec_b = payload["recommendations"][1]
        self.assertIn("missing_email", rec_b["risk_flags"])
        self.assertIn("missing_profile_url", rec_b["risk_flags"])
        self.assertIn("missing_interests", rec_b["risk_flags"])

    def test_low_prescreen_tier_risk_flag(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            self._write_input_files(pool_dir)

            prescreen_path = pool_dir / "清华大学" / "计算机科学与技术系" / "prescreen.json"
            prescreen = json.loads(prescreen_path.read_text(encoding="utf-8"))
            prescreen["top_candidates"][0]["tier"] = "C"
            prescreen_path.write_text(json.dumps(prescreen, ensure_ascii=False, indent=2), encoding="utf-8")

            payload = run_prescreen_closed_loop(
                school="清华大学",
                college="计算机科学与技术系",
                pool_dir=pool_dir,
            )

        self.assertIn("low_prescreen_tier", payload["recommendations"][0]["risk_flags"])

    def test_save_recommendations_writes_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            out_dir = Path(temp_dir) / "out"
            self._write_input_files(pool_dir)

            payload = run_prescreen_closed_loop(
                school="清华大学",
                college="计算机科学与技术系",
                pool_dir=pool_dir,
            )

            saved_path = save_recommendations(out_dir=out_dir, payload=payload)
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.name, "prescreen_recommendations.json")

            saved = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["school"], "清华大学")
            self.assertEqual(len(saved["recommendations"]), 2)

    def test_fail_fast_on_missing_teachers_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            target_dir = pool_dir / "清华大学" / "计算机科学与技术系"
            target_dir.mkdir(parents=True, exist_ok=True)

            with self.assertRaises(FileNotFoundError):
                run_prescreen_closed_loop(
                    school="清华大学",
                    college="计算机科学与技术系",
                    pool_dir=pool_dir,
                )

    def test_fail_fast_on_name_not_in_teachers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pool_dir = Path(temp_dir) / "pool"
            self._write_input_files(pool_dir)

            prescreen_path = pool_dir / "清华大学" / "计算机科学与技术系" / "prescreen.json"
            prescreen = json.loads(prescreen_path.read_text(encoding="utf-8"))
            prescreen["top_candidates"][0]["name"] = "不存在的人"
            prescreen_path.write_text(json.dumps(prescreen, ensure_ascii=False, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                run_prescreen_closed_loop(
                    school="清华大学",
                    college="计算机科学与技术系",
                    pool_dir=pool_dir,
                )


if __name__ == "__main__":
    unittest.main()
