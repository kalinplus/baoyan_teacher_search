from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import requests


NAVIGATION_BLACKLIST = {
    "首页",
    "上页",
    "下页",
    "尾页",
    "学院",
    "学校",
    "通知",
    "新闻",
    "公告",
    "招生",
    "下载",
    "联系我们",
    "师资队伍",
}
CHINESE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,4}$")


@dataclass(frozen=True)
class SourceRecord:
    school: str
    college: str
    url: str


@dataclass(frozen=True)
class Rule:
    name: str
    matcher: Callable[[str], bool]
    extractor: Callable[[str], List[str]]


def normalize_text(value: str) -> str:
    return value.strip()


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


def fetch_html(url: str, timeout: int) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def clean_teacher_names(candidates: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()

    for candidate in candidates:
        normalized = re.sub(r"\s+", "", candidate.strip())
        if not normalized:
            continue
        if normalized in NAVIGATION_BLACKLIST:
            continue
        if not CHINESE_NAME_PATTERN.fullmatch(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def validate_teachers(teachers: List[str], record: SourceRecord) -> None:
    if not teachers:
        raise RuntimeError(f"No teachers extracted for {record.school} / {record.college}")
    if len(teachers) != len(set(teachers)):
        raise RuntimeError(f"Duplicate names detected after cleaning for {record.school} / {record.college}")


def pick_rule(url: str, rules: List[Rule]) -> Rule:
    for rule in rules:
        if rule.matcher(url):
            return rule
    raise ValueError(f"No extraction rule configured for url: {url}")


def collect_teachers(record: SourceRecord, timeout: int, rules: List[Rule], logger) -> Dict[str, object]:
    logger.info("Collecting teachers for school=%s college=%s", record.school, record.college)
    rule = pick_rule(record.url, rules)
    html = fetch_html(record.url, timeout=timeout)
    candidates = rule.extractor(html)
    teachers = clean_teacher_names(candidates)
    validate_teachers(teachers, record)

    logger.info("Extraction done with rule=%s, teacher_count=%s", rule.name, len(teachers))
    return {
        "school": record.school,
        "college": record.college,
        "url": record.url,
        "teachers": teachers,
    }


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
        for teacher in result["teachers"]:
            lines.append(
                json.dumps(
                    {
                        "school": school,
                        "college": college,
                        "teacher": teacher,
                        "url": url,
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
