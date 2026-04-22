#!/usr/bin/env python3
"""Task1 batch closed loop: prescreen top candidates -> author_id -> scholar -> final recommendations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from scholar.author_id_resolver import UNIVERSITY_CONFIG_PATH, load_university_mapping, normalize_school_name
from scholar.author_disambiguation import resolve_teacher_author_id
from scholar.recommendation_assembler import assemble_final_recommendations
from scholar.scholar_batch_runner import run_scholar_batch
from utils import configure_logging, get_logger


ROOT_DIR = Path(__file__).resolve().parent.parent
logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch closed loop from prescreen top candidates")
    parser.add_argument("--school", required=True, help="School name or alias")
    parser.add_argument("--college", required=True, help="College name")
    parser.add_argument("--pool-dir", default="output/teacher_pool", help="Teacher pool root directory")
    parser.add_argument("--out-dir", default="output", help="Output root directory")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Input file must be a JSON object: {path}")
    return payload


def _validate_top_candidates(teachers_payload: Dict[str, Any], prescreen_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    teacher_profiles = teachers_payload.get("teacher_profiles")
    if not isinstance(teacher_profiles, list):
        raise ValueError("teachers.json missing teacher_profiles array")

    known_teachers = {
        str(item.get("name", "")).strip()
        for item in teacher_profiles
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }
    if not known_teachers:
        raise ValueError("teachers.json teacher_profiles has no valid names")

    top_candidates = prescreen_payload.get("top_candidates")
    if not isinstance(top_candidates, list):
        raise ValueError("prescreen.json missing top_candidates array")

    for index, item in enumerate(top_candidates):
        if not isinstance(item, dict):
            raise ValueError(f"top_candidates[{index}] must be an object")
        teacher_name = str(item.get("name", "")).strip()
        if not teacher_name:
            raise ValueError(f"top_candidates[{index}].name is required")
        if teacher_name not in known_teachers:
            raise ValueError(f"top_candidates[{index}].name not found in teachers.json: {teacher_name}")

    return top_candidates


def run_batch_closed_loop(
    *,
    school: str,
    college: str,
    pool_dir: Path,
    out_dir: Path,
    timeout: int,
) -> Dict[str, Any]:
    university_mapping = load_university_mapping(UNIVERSITY_CONFIG_PATH)
    canonical_school = normalize_school_name(school, university_mapping)

    source_dir = pool_dir / canonical_school / college
    teachers_payload = _load_json(source_dir / "teachers.json")
    prescreen_payload = _load_json(source_dir / "prescreen.json")
    top_candidates = _validate_top_candidates(teachers_payload, prescreen_payload)

    cache_path = out_dir / ".cache" / "author_id_cache.json"
    resolved_candidates: List[Dict[str, Any]] = []
    failed_candidates: List[Dict[str, Any]] = []

    for candidate in top_candidates:
        teacher_name = str(candidate["name"])
        try:
            result = resolve_teacher_author_id(
                school=canonical_school,
                teacher=teacher_name,
                cache_path=cache_path,
                timeout=timeout,
            )
        except Exception as exc:
            failed_candidates.append(
                {
                    "teacher": teacher_name,
                    "stage": "author_disambiguation",
                    "skip_reason": None,
                    "error": str(exc),
                }
            )
            continue
        if result["status"] == "skip":
            failed_candidates.append(
                {
                    "teacher": teacher_name,
                    "stage": "author_disambiguation",
                    "skip_reason": result["skip_reason"],
                    "error": result["error"],
                }
            )
            continue
        resolved_candidates.append(result)

    scholar_results: List[Dict[str, Any]] = []
    for resolved in resolved_candidates:
        teacher_name = str(resolved["teacher"])
        try:
            batch_results = run_scholar_batch(resolved_candidates=[resolved], timeout=timeout)
        except Exception as exc:
            failed_candidates.append(
                {
                    "teacher": teacher_name,
                    "stage": "scholar_batch",
                    "skip_reason": None,
                    "error": str(exc),
                }
            )
            continue

        if not batch_results:
            failed_candidates.append(
                {
                    "teacher": teacher_name,
                    "stage": "scholar_batch",
                    "skip_reason": None,
                    "error": "empty_scholar_result",
                }
            )
            continue

        scholar_item = batch_results[0]
        if str(scholar_item.get("status", "")) != "success":
            failed_candidates.append(
                {
                    "teacher": teacher_name,
                    "stage": "scholar_batch",
                    "skip_reason": None,
                    "error": str(scholar_item.get("error", "unknown_scholar_error")),
                }
            )
            continue

        scholar_results.append(scholar_item)

    final_payload = assemble_final_recommendations(
        school=canonical_school,
        college=college,
        top_candidates=top_candidates,
        resolved_candidates=resolved_candidates,
        scholar_results=scholar_results,
        failed_candidates=failed_candidates,
    )
    return final_payload


def save_final_recommendations(*, out_dir: Path, payload: Dict[str, Any]) -> Path:
    school = str(payload["school"])
    college = str(payload["college"])
    target_dir = out_dir / school / college
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / "final_recommendations.json"
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def main() -> int:
    load_dotenv(dotenv_path=ROOT_DIR / ".env")

    args = parse_args()
    configure_logging(args.log_level)

    final_payload = run_batch_closed_loop(
        school=args.school,
        college=args.college,
        pool_dir=Path(args.pool_dir),
        out_dir=Path(args.out_dir),
        timeout=args.timeout,
    )
    saved_path = save_final_recommendations(out_dir=Path(args.out_dir), payload=final_payload)

    logger.info("Saved final recommendations: %s", saved_path)
    print(f"Saved: {saved_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
