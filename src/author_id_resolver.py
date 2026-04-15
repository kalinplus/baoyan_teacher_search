#!/usr/bin/env python3
"""Stage-2 Step2: resolve Google Scholar author_id from school + teacher."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote

import requests
from dotenv import load_dotenv

from utils import configure_logging, get_logger


ROOT_DIR = Path(__file__).resolve().parent.parent
UNIVERSITY_CONFIG_PATH = ROOT_DIR / "config" / "universities.json"
SCRAPER_ENDPOINT = "https://api.scraperapi.com/"
AUTHOR_ID_PATTERN = re.compile(r"scholar\.google\.com/citations\?user=([A-Za-z0-9_-]+)")
logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Google Scholar author_id by school + teacher")
    parser.add_argument("--school", required=True, help="School name or alias")
    parser.add_argument("--teacher", required=True, help="Teacher name")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def load_university_mapping(config_path: Path) -> Dict[str, List[str]]:
    if not config_path.exists():
        raise FileNotFoundError(f"University mapping not found: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    return value.strip().casefold()


def normalize_school_name(raw_school: str, mapping: Dict[str, List[str]]) -> str:
    lookup: Dict[str, str] = {}
    for canonical, aliases in mapping.items():
        lookup[normalize_text(canonical)] = canonical
        for alias in aliases:
            lookup[normalize_text(alias)] = canonical

    normalized = lookup.get(normalize_text(raw_school))
    if normalized:
        return normalized
    raise ValueError(f"Unknown school alias: {raw_school}")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class AuthorIdResolver:
    """Resolve author_id from Google search results with local cache."""

    def __init__(self, scraperapi_key: str, timeout: int = 30):
        if not scraperapi_key:
            raise RuntimeError("Missing environment variable: SCRAPERAPI_KEY")
        self.scraperapi_key = scraperapi_key
        self.timeout = timeout
        logger.debug("AuthorIdResolver initialized with timeout=%s", timeout)

    def resolve(
        self,
        school: str,
        teacher: str,
        cache_path: Path,
        school_aliases: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        logger.info("Start resolving author_id for school=%s, teacher=%s", school, teacher)
        teacher_name = teacher.strip()
        if not teacher_name:
            raise ValueError("Teacher name cannot be empty")
        if teacher_name != teacher:
            logger.debug("Teacher name normalized from '%s' to '%s'", teacher, teacher_name)
        if not self._is_ascii_text(teacher_name):
            logger.warning(
                "Teacher query '%s' contains non-ASCII characters; Chinese-name search may be inaccurate",
                teacher_name,
            )

        cache = load_json(cache_path)
        cache_key = f"{school}::{teacher_name}"
        logger.debug("Loaded cache from %s, cache size=%s", cache_path, len(cache))
        cached_author_id = cache.get(cache_key)
        if cached_author_id:
            logger.info("Cache hit for key=%s, author_id=%s", cache_key, cached_author_id)
            return {
                "author_id": cached_author_id,
                "source": "author_id_cache",
                "matched_school": school,
                "matched_teacher": teacher_name,
            }

        logger.info("Cache miss for key=%s, start querying search engine", cache_key)

        candidate_ids = self.search_candidates(
            teacher=teacher_name,
            school=school,
            school_aliases=school_aliases,
        )
        if not candidate_ids:
            logger.error("No candidates found for school=%s, teacher=%s", school, teacher_name)
            raise RuntimeError("No author_id found from Google Search results")

        author_id = candidate_ids[0]
        logger.info(
            "Resolved author_id=%s using first candidate (candidate_count=%s)",
            author_id,
            len(candidate_ids),
        )
        cache[cache_key] = author_id
        save_json(cache_path, cache)
        logger.debug("Updated cache path=%s with key=%s", cache_path, cache_key)

        return {
            "author_id": author_id,
            "source": "google_search",
            "matched_school": school,
            "matched_teacher": teacher_name,
        }

    @staticmethod
    def _dedupe_terms(values: List[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values:
            normalized = value.strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    @staticmethod
    def _is_ascii_text(value: str) -> bool:
        return value.isascii()

    @classmethod
    def _build_query_terms(cls, school: str, school_aliases: Optional[List[str]]) -> List[str]:
        if not school_aliases:
            return [school]

        deduped = cls._dedupe_terms([*school_aliases, school])
        ascii_terms = [term for term in deduped if cls._is_ascii_text(term)]
        non_ascii_terms = [term for term in deduped if not cls._is_ascii_text(term)]
        return [*ascii_terms, *non_ascii_terms]

    @classmethod
    def _pick_school_abbreviation(cls, school: str, school_aliases: Optional[List[str]]) -> str:
        terms = cls._build_query_terms(school=school, school_aliases=school_aliases)
        abbreviations = [
            term
            for term in terms
            if cls._is_ascii_text(term) and re.fullmatch(r"[A-Z]{2,10}", term)
        ]
        if not abbreviations:
            raise ValueError(f"No uppercase ASCII school abbreviation found for school: {school}")
        return abbreviations[0]

    @classmethod
    def _build_query(cls, teacher: str, school: str, school_aliases: Optional[List[str]]) -> str:
        school_term = cls._pick_school_abbreviation(school=school, school_aliases=school_aliases)
        return f"site:scholar.google.com/citations {school_term} {teacher}"

    def search_candidates(
        self,
        teacher: str,
        school: str,
        school_aliases: Optional[List[str]] = None,
        max_candidates: int = 2,
    ) -> List[str]:
        seen = set()
        author_ids: List[str] = []
        query = self._build_query(teacher=teacher, school=school, school_aliases=school_aliases)
        logger.debug("Built single query for school=%s, teacher=%s: %s", school, teacher, query)

        google_url = f"https://www.google.com/search?q={quote(query)}&hl=en&num=10&start=0"
        logger.debug("Requesting search page start=0 with URL=%s", google_url)
        response = requests.get(
            SCRAPER_ENDPOINT,
            params={
                "api_key": self.scraperapi_key,
                "url": google_url,
                "render": "false",
                "country_code": "us",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        logger.debug("Search request succeeded, response_length=%s", len(response.text))

        decoded = unquote(response.text)

        for match in AUTHOR_ID_PATTERN.finditer(decoded):
            author_id = match.group(1)
            if author_id in seen:
                logger.debug("Skip duplicate candidate author_id=%s", author_id)
                continue
            seen.add(author_id)
            author_ids.append(author_id)
            logger.debug("Captured candidate author_id=%s", author_id)
            if len(author_ids) >= max_candidates:
                logger.info("Reached max_candidates=%s, stop searching", max_candidates)
                return author_ids

        if author_ids:
            logger.info("Found %s candidates from the single query", len(author_ids))
            return author_ids

        logger.info("No candidates found from the single query")
        return author_ids


def main() -> int:
    load_dotenv()
    args = parse_args()
    configure_logging(args.log_level)

    logger.info(
        "Start author_id resolver with school=%s, teacher=%s, out_dir=%s, timeout=%s",
        args.school,
        args.teacher,
        args.out_dir,
        args.timeout,
    )

    scraperapi_key = os.getenv("SCRAPERAPI_KEY", "").strip()
    resolver = AuthorIdResolver(scraperapi_key=scraperapi_key, timeout=args.timeout)

    university_mapping = load_university_mapping(UNIVERSITY_CONFIG_PATH)
    logger.debug("Loaded university mapping entries=%s from %s", len(university_mapping), UNIVERSITY_CONFIG_PATH)
    canonical_school = normalize_school_name(args.school, university_mapping)
    logger.info("Normalized school '%s' -> '%s'", args.school, canonical_school)

    cache_path = Path(args.out_dir) / ".cache" / "author_id_cache.json"
    logger.debug("Using cache path: %s", cache_path)
    result = resolver.resolve(
        school=canonical_school,
        teacher=args.teacher,
        cache_path=cache_path,
        school_aliases=university_mapping.get(canonical_school, []),
    )
    logger.info("Resolve completed with author_id=%s, source=%s", result["author_id"], result["source"])

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
