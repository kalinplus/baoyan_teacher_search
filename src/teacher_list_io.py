from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from teacher_list_helpers import normalize_text
from teacher_list_models import SourceRecord


def load_source_records(path: Path) -> List[SourceRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Input source file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input source file must be a JSON array")

    records: List[SourceRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Source record at index {index} must be an object")

        school = normalize_text(str(item.get("school", "")))
        college = normalize_text(str(item.get("college", "")))
        url = normalize_text(str(item.get("url", "")))
        if not school or not college or not url:
            raise ValueError(f"Source record at index {index} missing required fields")

        records.append(SourceRecord(school=school, college=college, url=url))

    return records


def save_result(out_dir: Path, payload: Dict[str, object]) -> Path:
    school = str(payload["school"])
    college = str(payload["college"])
    target_dir = out_dir / school / college
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / "teachers.json"
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def export_jsonl(path: Path, results: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []

    for result in results:
        school = str(result["school"])
        college = str(result["college"])
        url = str(result["url"])
        profile_map = {
            str(item.get("name", "")): item
            for item in result.get("teacher_profiles", [])
            if isinstance(item, dict)
        }

        for teacher in result["teachers"]:
            profile = profile_map.get(str(teacher), {})
            lines.append(
                json.dumps(
                    {
                        "school": school,
                        "college": college,
                        "teacher": teacher,
                        "url": url,
                        "profile_url": profile.get("profile_url"),
                        "email": profile.get("email"),
                        "interests": profile.get("interests", []),
                        "title": profile.get("title"),
                        "source_url": profile.get("source_url", url),
                    },
                    ensure_ascii=False,
                )
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_direct_record(school: str, college: str, url: str) -> SourceRecord:
    school_name = normalize_text(school)
    college_name = normalize_text(college)
    url_value = normalize_text(url)
    if not school_name or not college_name or not url_value:
        raise ValueError("Direct mode requires non-empty --school --college --url")
    return SourceRecord(school=school_name, college=college_name, url=url_value)


def select_records(args: argparse.Namespace) -> List[SourceRecord]:
    if args.url:
        return [build_direct_record(args.school, args.college, args.url)]

    records = load_source_records(Path(args.input))
    if not args.school and not args.college:
        return records

    filtered = [
        item
        for item in records
        if (not args.school or item.school == normalize_text(args.school))
        and (not args.college or item.college == normalize_text(args.college))
    ]
    if not filtered:
        raise ValueError("No source record matched --school/--college filters")
    return filtered


def save_prescreen_result(out_dir: Path, payload: Dict[str, object]) -> Path:
    school = str(payload["school"])
    college = str(payload["college"])
    target_dir = out_dir / school / college
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / "prescreen.json"
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path
