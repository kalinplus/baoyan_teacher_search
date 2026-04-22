#!/usr/bin/env python3
"""Step3: LLM-powered teacher profile extraction (basic + extended layers)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from utils import configure_logging, get_logger

from llm.llm_client import LLMClient
from llm.prompts import BASIC_EXTRACT_PROMPT, EXTENDED_EXTRACT_PROMPT

logger = get_logger(__name__)

DEFAULT_DELAY = 0.5


def _get_full_text(teacher: Dict[str, Any]) -> Optional[str]:
    homepage = teacher.get("homepage")
    if isinstance(homepage, dict):
        return homepage.get("full_text")
    return None


def _get_homepage_url(teacher: Dict[str, Any]) -> Optional[str]:
    homepage = teacher.get("homepage")
    if isinstance(homepage, dict):
        return homepage.get("personal_homepage")
    return None


def fetch_homepage_text(url: str, timeout: int = 30) -> str:
    import re
    from html import unescape

    import requests

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = unescape(text)
    lines = [line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 2]
    return "\n".join(lines)


def extract_one_profile(client: LLMClient, teacher: Dict[str, Any]) -> Dict[str, Any]:
    result = {"name": teacher["name"]}

    full_text = _get_full_text(teacher)
    if not full_text:
        result["skip_reason"] = "no_full_text"
        return result

    try:
        basic = client.extract_structured(BASIC_EXTRACT_PROMPT, full_text)
        result["llm_basic"] = basic
    except Exception as exc:
        logger.warning("LLM basic extraction failed for %s: %s", teacher["name"], exc)
        result["error"] = str(exc)
        return result

    homepage_url = _get_homepage_url(teacher)
    if homepage_url:
        try:
            homepage_text = fetch_homepage_text(homepage_url)
            if homepage_text:
                extended = client.extract_structured(EXTENDED_EXTRACT_PROMPT, homepage_text)
                result["llm_extended"] = extended
        except Exception as exc:
            logger.warning("LLM extended extraction failed for %s: %s", teacher["name"], exc)
            result["llm_extended_error"] = str(exc)

    return result


def run_extraction(
    input_path: str,
    output_path: str,
    delay: float = DEFAULT_DELAY,
) -> Dict[str, int]:
    client = LLMClient()
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    profiles = data.get("teacher_profiles", [])

    stats = {"total": len(profiles), "success": 0, "skipped": 0, "failed": 0}
    results = []

    for i, teacher in enumerate(profiles):
        name = teacher["name"]
        logger.info("[%d/%d] Processing %s...", i + 1, len(profiles), name)

        result = extract_one_profile(client, teacher)

        if result.get("skip_reason"):
            stats["skipped"] += 1
        elif result.get("error"):
            stats["failed"] += 1
        else:
            stats["success"] += 1

        merged = {**teacher, **result}
        results.append(merged)

        data["teacher_profiles"] = results
        Path(output_path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if i < len(profiles) - 1:
            time.sleep(delay)

    logger.info("Extraction complete: %s", stats)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-powered teacher profile extraction")
    parser.add_argument("--input", required=True, help="Input teachers.json path")
    parser.add_argument("--output", required=True, help="Output llm_enriched.json path")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between API calls")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")
    configure_logging(args.log_level)
    stats = run_extraction(args.input, args.output, delay=args.delay)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
