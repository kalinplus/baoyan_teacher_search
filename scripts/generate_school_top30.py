import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from teacher_list_prescreen import (
    load_prescreen_scoring_config,
    load_contacted_teachers,
    run_offline_prescreen,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEACHER_POOL_DIR = PROJECT_ROOT / "output" / "teacher_pool"
OUTPUT_PATH = PROJECT_ROOT / "output" / "school_top30.json"
CONTACTED_PATH = PROJECT_ROOT / "config" / "contacted_teachers.json"
CONFIG_PATH = PROJECT_ROOT / "config" / "prescreen_scoring.json"


def main():
    config = load_prescreen_scoring_config(CONFIG_PATH)
    keywords = list(config.get("interest_target_keywords", []))
    negative_keywords = list(config.get("negative_interest_keywords", []))
    contacted = load_contacted_teachers(CONTACTED_PATH)

    school_results = {}

    for school_dir in sorted(TEACHER_POOL_DIR.iterdir()):
        if not school_dir.is_dir():
            continue
        school_name = school_dir.name
        teachers_json_files = list(school_dir.rglob("teachers.json"))
        # dedupe by (school, college) from payload to avoid stale duplicates
        seen_colleges: set[str] = set()
        college_candidates = []
        for teachers_json in sorted(teachers_json_files, key=lambda p: str(p)):
            payload = json.loads(teachers_json.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "teacher_profiles" not in payload:
                continue
            college_name = payload.get("college", "")
            if not college_name:
                continue
            college_key = f"{payload.get('school', '')}/{college_name}"
            if college_key in seen_colleges:
                continue
            seen_colleges.add(college_key)

            try:
                result = run_offline_prescreen(
                    payload,
                    top_n=9999,
                    budget=9999,
                    keywords=keywords,
                    contacted_teachers=contacted,
                    negative_keywords=negative_keywords,
                    scoring_config_path=CONFIG_PATH,
                )
            except Exception as exc:
                print(f"Skip {school_name}/{college_name}: {exc}")
                continue

            scored = result["candidates"]
            college_candidates.append({
                "college": college_name,
                "candidates": scored,
            })

        n_colleges = len(college_candidates)
        if n_colleges == 0:
            continue

        base_quota = 30 // n_colleges
        remainder = 30 % n_colleges

        selected = []
        next_best = []
        for cc in college_candidates:
            cands = cc["candidates"]
            for i in range(min(base_quota, len(cands))):
                selected.append({
                    "school": school_name,
                    "college": cc["college"],
                    **cands[i],
                })
            if len(cands) > base_quota:
                next_best.append({
                    "school": school_name,
                    "college": cc["college"],
                    **cands[base_quota],
                })

        if remainder > 0:
            next_best.sort(key=lambda x: (-x["score"], x["name"]))
            for item in next_best[:remainder]:
                selected.append(item)

        selected.sort(key=lambda x: (-x["score"], x["name"]))
        # trim to exactly 30 if over
        selected = selected[:30]

        school_results[school_name] = {
            "total_colleges": n_colleges,
            "base_quota": base_quota,
            "remainder": remainder,
            "selected_count": len(selected),
            "teachers": [
                {
                    "rank": i + 1,
                    "name": s["name"],
                    "score": s["score"],
                    "tier": s["tier"],
                    "college": s["college"],
                    "matched_keywords": s.get("matched_keywords", []),
                    "matched_negative_keywords": s.get("matched_negative_keywords", []),
                    "reasons": s.get("reasons", []),
                }
                for i, s in enumerate(selected)
            ],
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(school_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Done. Written to {OUTPUT_PATH}")
    for school, data in school_results.items():
        print(f"  {school}: {data['selected_count']} teachers from {data['total_colleges']} colleges")


if __name__ == "__main__":
    main()
