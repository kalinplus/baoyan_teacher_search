#!/usr/bin/env python3
"""Task0 Step2: collect teacher names and rich profiles from college list pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teacher_extractors import get_rules
from teacher_list_core import collect_teachers
from teacher_list_io import export_jsonl, save_prescreen_result, save_result, select_records
from teacher_list_prescreen import load_contacted_teachers, parse_keyword_csv, run_offline_prescreen
from utils import configure_logging, get_logger


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT_DIR / "docs" / "task0" / "source_urls.json"
DEFAULT_CONTACTED_PATH = ROOT_DIR / "config" / "contacted_teachers.json"
logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect teachers from college list pages")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH), help="Input JSON file path")
    parser.add_argument("--school", default="", help="Target school")
    parser.add_argument("--college", default="", help="Target college")
    parser.add_argument("--url", default="", help="Direct target URL for single-source run")
    parser.add_argument("--out-dir", default="output/teacher_pool", help="Output directory")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--export-jsonl", default="", help="Optional export path for all teachers jsonl")
    parser.add_argument("--prescreen", action="store_true", help="Run offline prescreen and output prescreen.json")
    parser.add_argument("--prescreen-dir", default="", help="Read teachers.json from this directory for prescreen (skip collection)")
    parser.add_argument("--top-n", type=int, default=20, help="Top N candidates selected for next stage")
    parser.add_argument("--budget", type=int, default=20, help="Max candidate budget for next stage")
    parser.add_argument("--keywords", default="", help="Comma-separated keyword hints for interest matching")
    parser.add_argument("--negative-keywords", default="", help="Comma-separated negative interest keywords for penalty")
    parser.add_argument(
        "--contacted-list",
        default=str(DEFAULT_CONTACTED_PATH),
        help="Contacted teachers config JSON path",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def _prescreen_from_dir(base_dir: Path, args: argparse.Namespace) -> int:
    contacted_teachers = load_contacted_teachers(Path(args.contacted_list))
    keywords = parse_keyword_csv(args.keywords)
    negative_keywords = parse_keyword_csv(args.negative_keywords)

    for teachers_json in sorted(base_dir.rglob("teachers.json")):
        payload = json.loads(teachers_json.read_text(encoding="utf-8"))
        prescreen_payload = run_offline_prescreen(
            payload,
            top_n=args.top_n,
            budget=args.budget,
            keywords=keywords,
            negative_keywords=negative_keywords,
            contacted_teachers=contacted_teachers,
        )
        prescreen_saved = save_prescreen_result(base_dir, prescreen_payload)
        logger.info("Prescreen %s: %d candidates, saved %s", teachers_json.parent.name, len(prescreen_payload["top_candidates"]), prescreen_saved)
        print(f"Saved: {prescreen_saved}")

    return 0


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)

    if args.prescreen_dir:
        return _prescreen_from_dir(Path(args.prescreen_dir), args)

    rules = get_rules()
    records = select_records(args)
    out_dir = Path(args.out_dir)
    keywords = parse_keyword_csv(args.keywords)
    negative_keywords = parse_keyword_csv(args.negative_keywords)
    contacted_teachers = load_contacted_teachers(Path(args.contacted_list)) if args.prescreen else {}

    results = []
    allow_partial_export = bool(args.export_jsonl) and not args.school and not args.college and not args.url

    for record in records:
        try:
            payload = collect_teachers(record, timeout=args.timeout, rules=rules, logger=logger)
            saved = save_result(out_dir, payload)
            logger.info("Saved teacher list: %s", saved)
            print(f"Saved: {saved}")

            if args.prescreen:
                prescreen_payload = run_offline_prescreen(
                    payload,
                    top_n=args.top_n,
                    budget=args.budget,
                    keywords=keywords,
                    negative_keywords=negative_keywords,
                    contacted_teachers=contacted_teachers,
                )
                prescreen_saved = save_prescreen_result(out_dir, prescreen_payload)
                logger.info("Saved prescreen result: %s", prescreen_saved)
                print(f"Saved: {prescreen_saved}")

            results.append(payload)
        except Exception as exc:
            if not allow_partial_export:
                raise

            cached_path = out_dir / record.school / record.college / "teachers.json"
            if cached_path.exists():
                cached_payload = json.loads(cached_path.read_text(encoding="utf-8"))
                logger.warning("Collect failed, fallback cached result %s, reason=%s", cached_path, exc)
                results.append(cached_payload)
                continue

            logger.warning("Collect failed and no cached result, skip %s/%s, reason=%s", record.school, record.college, exc)

    if args.export_jsonl:
        export_path = Path(args.export_jsonl)
        export_jsonl(export_path, results)
        logger.info("Saved jsonl export: %s", export_path)
        print(f"Saved: {export_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
