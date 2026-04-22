#!/usr/bin/env python3
"""End-to-end LLM pipeline: extraction + matching."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from utils import configure_logging, get_logger

from llm.profile_extractor import run_extraction
from llm.match_engine import run_matching

logger = get_logger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def run_pipeline(
    input_path: str,
    resume_path: str,
    interests_path: str,
    output_dir: str,
    delay: float = 0.5,
) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    enriched_path = str(out / "llm_enriched.json")
    recommendations_path = str(out / "recommendations.json")

    logger.info("Step 1/2: LLM extraction (%s -> %s)", input_path, enriched_path)
    ext_stats = run_extraction(input_path, enriched_path, delay=delay)
    print(json.dumps(ext_stats, indent=2))

    if ext_stats["success"] == 0 and ext_stats["skipped"] == ext_stats["total"]:
        logger.error("No teachers extracted, aborting matching")
        sys.exit(1)

    logger.info("Step 2/2: LLM matching (%s -> %s)", enriched_path, recommendations_path)
    match_stats = run_matching(
        enriched_path, resume_path, interests_path, recommendations_path, delay=delay
    )
    print(json.dumps(match_stats, indent=2))

    logger.info("Done. Recommendations at %s", recommendations_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="End-to-end LLM pipeline: extract teacher info then match with resume"
    )
    p.add_argument("--input", required=True, help="Input teachers.json (with scraped full_text)")
    p.add_argument("--resume", required=True, help="Resume text file")
    p.add_argument("--interests", required=True, help="Research interests text file")
    p.add_argument("--output-dir", required=True, help="Output directory for results")
    p.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(dotenv_path=ROOT_DIR / ".env")
    configure_logging(args.log_level)
    run_pipeline(
        input_path=args.input,
        resume_path=args.resume,
        interests_path=args.interests,
        output_dir=args.output_dir,
        delay=args.delay,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
