#!/usr/bin/env python3
"""Prescreen-only closed loop: teachers + prescreen -> recommendations (no Scholar API needed)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate recommendations from prescreen results without Scholar API")
    parser.add_argument("--school", required=True, help="School name or alias")
    parser.add_argument("--college", required=True, help="College name")
    parser.add_argument("--pool-dir", default="output/teacher_pool", help="Teacher pool root directory")
    parser.add_argument("--out-dir", default="output", help="Output root directory")
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Input file must be a JSON object: {path}")
    return payload


def _validate_and_merge(
    teachers_payload: Dict[str, Any],
    prescreen_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    teacher_profiles = teachers_payload.get("teacher_profiles")
    if not isinstance(teacher_profiles, list):
        raise ValueError("teachers.json missing teacher_profiles array")

    profile_by_name = {
        str(item.get("name", "")).strip(): item
        for item in teacher_profiles
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }

    top_candidates = prescreen_payload.get("top_candidates")
    if not isinstance(top_candidates, list):
        raise ValueError("prescreen.json missing top_candidates array")

    merged: List[Dict[str, Any]] = []
    for index, item in enumerate(top_candidates):
        if not isinstance(item, dict):
            raise ValueError(f"top_candidates[{index}] must be an object")
        teacher_name = str(item.get("name", "")).strip()
        if not teacher_name:
            raise ValueError(f"top_candidates[{index}].name is required")

        profile = profile_by_name.get(teacher_name)
        if not profile:
            raise ValueError(f"top_candidates[{index}].name not found in teachers.json: {teacher_name}")

        merged.append({"prescreen": item, "profile": profile})

    return merged


def _build_risk_flags(prescreen: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
    flags: List[str] = []

    tier = str(prescreen.get("tier", ""))
    if tier == "C":
        flags.append("low_prescreen_tier")

    if not profile.get("email"):
        flags.append("missing_email")

    if not profile.get("profile_url"):
        flags.append("missing_profile_url")

    if not profile.get("interests"):
        flags.append("missing_interests")

    return flags


def assemble_prescreen_recommendations(
    *,
    school: str,
    college: str,
    merged_candidates: List[Dict[str, Any]],
    prescreen_stats: Dict[str, Any],
) -> Dict[str, Any]:
    recommendations: List[Dict[str, Any]] = []
    for item in merged_candidates:
        prescreen = item["prescreen"]
        profile = item["profile"]

        recommendations.append(
            {
                "teacher": str(prescreen["name"]),
                "rank": int(prescreen.get("rank", 0)),
                "prescreen_score": int(prescreen.get("score", 0)),
                "prescreen_tier": prescreen.get("tier"),
                "prescreen_reasons": list(prescreen.get("reasons", [])),
                "matched_keywords": list(prescreen.get("matched_keywords", [])),
                "profile": {
                    "profile_url": profile.get("profile_url"),
                    "email": profile.get("email"),
                    "title": profile.get("title"),
                    "interests": profile.get("interests", []),
                    "homepage": profile.get("homepage"),
                    "source_url": profile.get("source_url"),
                },
                "recommendation_reason": _build_recommendation_reason(prescreen),
                "risk_flags": _build_risk_flags(prescreen, profile),
            }
        )

    return {
        "school": school,
        "college": college,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "prescreen_only",
        "total_candidates": len(merged_candidates),
        "prescreen_stats": prescreen_stats,
        "recommendations": recommendations,
    }


def _build_recommendation_reason(prescreen: Dict[str, Any]) -> str:
    tier = str(prescreen.get("tier", ""))
    score = int(prescreen.get("score", 0))
    matched = list(prescreen.get("matched_keywords", []))
    keyword_part = f"; keywords={','.join(matched)}" if matched else ""
    return f"prescreen_tier={tier}; prescreen_score={score}{keyword_part}"


def run_prescreen_closed_loop(
    *,
    school: str,
    college: str,
    pool_dir: Path,
) -> Dict[str, Any]:
    source_dir = pool_dir / school / college
    teachers_payload = _load_json(source_dir / "teachers.json")
    prescreen_payload = _load_json(source_dir / "prescreen.json")

    merged = _validate_and_merge(teachers_payload, prescreen_payload)

    return assemble_prescreen_recommendations(
        school=school,
        college=college,
        merged_candidates=merged,
        prescreen_stats=prescreen_payload.get("stats", {}),
    )


def save_recommendations(*, out_dir: Path, payload: Dict[str, Any]) -> Path:
    school = str(payload["school"])
    college = str(payload["college"])
    target_dir = out_dir / school / college
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / "prescreen_recommendations.json"
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def main() -> int:
    args = parse_args()

    payload = run_prescreen_closed_loop(
        school=args.school,
        college=args.college,
        pool_dir=Path(args.pool_dir),
    )
    saved_path = save_recommendations(out_dir=Path(args.out_dir), payload=payload)

    print(f"Saved: {saved_path}")
    print(f"Recommendations: {len(payload['recommendations'])} / {payload['total_candidates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
