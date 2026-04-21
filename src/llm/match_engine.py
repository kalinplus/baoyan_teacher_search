#!/usr/bin/env python3
"""Step4: LLM-powered teacher matching and recommendation."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from utils import configure_logging, get_logger

from llm.llm_client import LLMClient
from llm.prompts import MATCH_PROMPT

logger = get_logger(__name__)

DEFAULT_DELAY = 0.5


def _build_teacher_summary(teacher: Dict[str, Any]) -> str:
    parts = [f"姓名: {teacher['name']}"]

    basic = teacher.get("llm_basic")
    if basic:
        if basic.get("title"):
            parts.append(f"职称: {basic['title']}")
        if basic.get("research_keywords"):
            parts.append(f"研究方向: {'、'.join(basic['research_keywords'])}")
        if basic.get("bio"):
            parts.append(f"简介: {basic['bio']}")

    extended = teacher.get("llm_extended")
    if extended:
        if extended.get("research_summary"):
            parts.append(f"研究总结: {extended['research_summary']}")
        if extended.get("recruiting_status"):
            parts.append(f"招生状态: {extended['recruiting_status']}")
        if extended.get("recruiting_targets"):
            parts.append(f"招生类型: {', '.join(extended['recruiting_targets'])}")
        if extended.get("recent_works"):
            works = [f"- {w['title']} ({w.get('venue', '')}, {w.get('year', '')})" for w in extended["recent_works"]]
            parts.append("代表作:\n" + "\n".join(works))
        if extended.get("awards"):
            parts.append(f"奖项: {'、'.join(extended['awards'])}")

    return "\n".join(parts)


def run_matching(
    input_path: str,
    resume_path: str,
    interests_path: str,
    output_path: str,
    delay: float = DEFAULT_DELAY,
) -> Dict[str, int]:
    client = LLMClient()
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    resume = Path(resume_path).read_text(encoding="utf-8").strip()
    interests = Path(interests_path).read_text(encoding="utf-8").strip()
    profiles = data.get("teacher_profiles", [])

    user_context = f"## 我的简历\n{resume}\n\n## 我的研究兴趣\n{interests}"

    stats = {"total": len(profiles), "matched": 0, "failed": 0}
    recommendations: List[Dict[str, Any]] = []

    for i, teacher in enumerate(profiles):
        name = teacher["name"]
        logger.info("[%d/%d] Matching %s...", i + 1, len(profiles), name)

        teacher_summary = _build_teacher_summary(teacher)
        user_prompt = f"## 教师信息\n{teacher_summary}\n\n{user_context}"

        try:
            result = client.extract_structured(MATCH_PROMPT, user_prompt)
            rec = {
                "teacher": name,
                "match_score": result.get("match_score", 0),
                "match_reasons": result.get("match_reasons", []),
                "risk_flags": result.get("risk_flags", []),
            }
            recommendations.append(rec)
            stats["matched"] += 1
        except Exception as exc:
            logger.warning("LLM matching failed for %s: %s", name, exc)
            stats["failed"] += 1

        output_data = {
            "school": data.get("school"),
            "college": data.get("college"),
            "recommendations": recommendations,
            "stats": stats,
        }
        Path(output_path).write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if i < len(profiles) - 1:
            time.sleep(delay)

    logger.info("Matching complete: %s", stats)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-powered teacher matching")
    parser.add_argument("--input", required=True, help="Input llm_enriched.json path")
    parser.add_argument("--resume", required=True, help="User resume text file")
    parser.add_argument("--interests", required=True, help="User research interests text file")
    parser.add_argument("--output", required=True, help="Output recommendations.json path")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between API calls")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)
    stats = run_matching(args.input, args.resume, args.interests, args.output, delay=args.delay)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
