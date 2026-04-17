#!/usr/bin/env python3
"""Task0 Step2: collect teacher names from college list pages with site-specific rules."""

from __future__ import annotations

import argparse
from pathlib import Path

from teacher_extractors import get_rules
from teacher_extractors.thu import extract_thu_cs_h2_anchor_names
from teacher_list_core import (
    clean_teacher_names,
    collect_teachers,
    export_jsonl,
    fetch_html,
    save_result,
    select_records,
)
from utils import configure_logging, get_logger


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT_DIR / "docs" / "task0" / "source_urls.json"
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
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)

    rules = get_rules()
    records = select_records(args)
    out_dir = Path(args.out_dir)

    results = [collect_teachers(record, timeout=args.timeout, rules=rules, logger=logger) for record in records]
    for payload in results:
        saved = save_result(out_dir, payload)
        logger.info("Saved teacher list: %s", saved)
        print(f"Saved: {saved}")

    if args.export_jsonl:
        export_path = Path(args.export_jsonl)
        export_jsonl(export_path, results)
        logger.info("Saved jsonl export: %s", export_path)
        print(f"Saved: {export_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
