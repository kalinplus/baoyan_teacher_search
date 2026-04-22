#!/usr/bin/env python3
"""Stage-2 Step2: resolve Google Scholar author_id from school + teacher."""

from __future__ import annotations

import argparse
from html import unescape
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote, unquote

import requests
from dotenv import load_dotenv
from pypinyin import Style, pinyin

from utils import configure_logging, get_logger


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
UNIVERSITY_CONFIG_PATH = ROOT_DIR / "config" / "universities.json"
COMPOUND_SURNAMES_CONFIG_PATH = ROOT_DIR / "config" / "compound_surnames.json"
SCRAPER_ENDPOINT = "https://api.scraperapi.com/"
AUTHOR_ID_PATTERN = re.compile(r"scholar\.google\.com/citations\?user=([A-Za-z0-9_-]+)")
SCHOLAR_PROFILE_NAME_PATTERN = re.compile(r"id=[\"']gsc_prf_in[\"'][^>]*>(.*?)<", re.IGNORECASE | re.DOTALL)
logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Google Scholar author_id by school + teacher")
    parser.add_argument("--school", required=True, help="School name or alias")
    parser.add_argument("--teacher", required=True, help="Teacher name")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
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


def load_compound_surnames(config_path: Path) -> Set[str]:
    if not config_path.exists():
        raise FileNotFoundError(f"Compound surnames config not found: {config_path}")

    raw_data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError(f"Compound surnames config must be a JSON array: {config_path}")

    normalized_surnames = set()
    for item in raw_data:
        if not isinstance(item, str):
            raise ValueError(f"Compound surname must be a string: {item!r}")
        surname = item.strip()
        if not surname:
            raise ValueError("Compound surname cannot be empty")
        normalized_surnames.add(surname)

    if not normalized_surnames:
        raise ValueError(f"Compound surnames config is empty: {config_path}")
    return normalized_surnames


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

    def __init__(
        self,
        scraperapi_key: str,
        timeout: int = 60,
        compound_surnames_path: Path = COMPOUND_SURNAMES_CONFIG_PATH,
    ):
        if not scraperapi_key:
            raise RuntimeError("Missing environment variable: SCRAPERAPI_KEY")
        self.scraperapi_key = scraperapi_key
        self.timeout = timeout
        self.max_attempts = 3
        self.retry_timeout_step = 30
        self.compound_surnames = load_compound_surnames(compound_surnames_path)
        logger.debug("AuthorIdResolver initialized with timeout=%s", timeout)

    def _request_with_retry(self, *, url: str, params: Dict[str, str]) -> requests.Response:
        for attempt in range(1, self.max_attempts + 1):
            attempt_timeout = self.timeout + (attempt - 1) * self.retry_timeout_step
            try:
                response = requests.get(
                    SCRAPER_ENDPOINT,
                    params={
                        "api_key": self.scraperapi_key,
                        "url": url,
                        **params,
                    },
                    timeout=attempt_timeout,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException:
                if attempt >= self.max_attempts:
                    raise
                logger.warning(
                    "Request failed, retrying attempt=%s/%s timeout=%ss url=%s",
                    attempt,
                    self.max_attempts,
                    attempt_timeout,
                    url,
                )

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

        teacher_input = self._normalize_teacher_input(teacher_name)
        teacher_query = teacher_input["teacher_query"]
        cache_teacher_name = teacher_input["cache_teacher_name"]
        if teacher_input["should_warn_ascii_input"]:
            logger.warning(
                "Teacher input '%s' is non-Chinese; skip cache write to avoid mixed-language cache keys",
                teacher_name,
            )
        else:
            logger.debug("Teacher query normalized to pinyin '%s' from Chinese input '%s'", teacher_query, teacher_name)

        cache = load_json(cache_path)
        logger.debug("Loaded cache from %s, cache size=%s", cache_path, len(cache))
        cache_key: Optional[str] = None
        if cache_teacher_name:
            cache_key = f"{school}::{cache_teacher_name}"
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
        else:
            logger.info("Skip cache for non-Chinese teacher input, start querying search engine")

        candidate_ids = self.search_candidates(
            teacher=teacher_query,
            school=school,
            school_aliases=school_aliases,
        )
        if not candidate_ids:
            logger.error("No candidates found for school=%s, teacher=%s", school, teacher_name)
            raise RuntimeError("No author_id found from Google Search results")

        author_id = candidate_ids[0]
        self._validate_candidate_by_cache_conflict(
            author_id=author_id,
            teacher_name=teacher_name,
            cache=cache,
        )
        self._validate_candidate_by_scholar_name(
            author_id=author_id,
            teacher_name=teacher_name,
        )
        logger.info(
            "Resolved author_id=%s using first candidate (candidate_count=%s)",
            author_id,
            len(candidate_ids),
        )
        if cache_key:
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
    def _compact_name(value: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", value).casefold()

    def _build_teacher_name_variants(self, teacher_name: str) -> List[str]:
        variants: List[str] = []
        compact_original = self._compact_name(teacher_name)
        if compact_original:
            variants.append(compact_original)

        if self._contains_cjk(teacher_name):
            surname, given_name = self._split_chinese_name(teacher_name, self.compound_surnames)
            surname_pinyin = "".join(self._to_pinyin_syllables(surname))
            given_name_pinyin = "".join(self._to_pinyin_syllables(given_name))
            if surname_pinyin and given_name_pinyin:
                variants.append(self._compact_name(f"{given_name_pinyin} {surname_pinyin}"))
                variants.append(self._compact_name(f"{surname_pinyin} {given_name_pinyin}"))

        deduped: List[str] = []
        seen = set()
        for item in variants:
            if not item or item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @classmethod
    def _is_same_teacher_name(cls, left: str, right: str) -> bool:
        left_compact = cls._compact_name(left)
        right_compact = cls._compact_name(right)
        if not left_compact or not right_compact:
            return False
        return left_compact == right_compact

    @staticmethod
    def _extract_teacher_from_cache_key(cache_key: str) -> Optional[str]:
        if "::" not in cache_key:
            return None
        _school, teacher = cache_key.split("::", 1)
        teacher_name = teacher.strip()
        if not teacher_name:
            return None
        return teacher_name

    def _validate_candidate_by_cache_conflict(
        self,
        *,
        author_id: str,
        teacher_name: str,
        cache: Dict[str, Any],
    ) -> None:
        for cache_key, cached_author_id in cache.items():
            if cached_author_id != author_id:
                continue
            cached_teacher_name = self._extract_teacher_from_cache_key(cache_key)
            if not cached_teacher_name:
                continue
            if self._is_same_teacher_name(cached_teacher_name, teacher_name):
                continue

            message = (
                "skip_reason=author_id_conflict_existing_teacher "
                f"author_id={author_id} cached_teacher={cached_teacher_name} current_teacher={teacher_name}"
            )
            logger.warning(message)
            raise RuntimeError(message)

    def _fetch_scholar_profile_name(self, author_id: str) -> str:
        scholar_url = f"https://scholar.google.com/citations?user={author_id}&hl=en"
        response = self._request_with_retry(
            url=scholar_url,
            params={
                "render": "false",
                "country_code": "us",
            },
        )

        decoded = unquote(response.text)
        match = SCHOLAR_PROFILE_NAME_PATTERN.search(decoded)
        if not match:
            raise RuntimeError(f"Cannot extract Scholar profile name for author_id={author_id}")

        profile_name = re.sub(r"<[^>]+>", "", unescape(match.group(1))).strip()
        if not profile_name:
            raise RuntimeError(f"Scholar profile name is empty for author_id={author_id}")
        return profile_name

    def _validate_candidate_by_scholar_name(self, *, author_id: str, teacher_name: str) -> None:
        profile_name = self._fetch_scholar_profile_name(author_id=author_id)
        profile_name_compact = self._compact_name(profile_name)
        if not profile_name_compact:
            raise RuntimeError(f"Scholar profile name is invalid for author_id={author_id}")

        teacher_name_variants = self._build_teacher_name_variants(teacher_name)
        if any(variant == profile_name_compact for variant in teacher_name_variants):
            return

        message = (
            "skip_reason=scholar_name_mismatch "
            f"author_id={author_id} scholar_name={profile_name} teacher={teacher_name}"
        )
        logger.warning(message)
        raise RuntimeError(message)

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

    @staticmethod
    def _contains_cjk(value: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", value))

    @staticmethod
    def _split_chinese_name(name: str, compound_surnames: Set[str]) -> tuple[str, str]:
        if len(name) >= 2 and name[:2] in compound_surnames:
            return name[:2], name[2:]
        return name[:1], name[1:]

    @staticmethod
    def _to_pinyin_syllables(value: str) -> List[str]:
        syllables: List[str] = []
        for item in pinyin(value, style=Style.NORMAL):
            if not item or not item[0]:
                continue
            syllables.append(item[0].strip().lower())
        return [syllable for syllable in syllables if syllable]

    def _normalize_teacher_input(self, teacher_name: str) -> Dict[str, Any]:
        if not self._contains_cjk(teacher_name):
            return {
                "teacher_query": teacher_name,
                "cache_teacher_name": None,
                "should_warn_ascii_input": True,
            }

        surname, given_name = self._split_chinese_name(teacher_name, self.compound_surnames)
        surname_pinyin = "".join(self._to_pinyin_syllables(surname)).capitalize()
        given_name_pinyin = "".join(self._to_pinyin_syllables(given_name)).capitalize()
        teacher_query = " ".join([part for part in [given_name_pinyin, surname_pinyin] if part]).strip()
        if not teacher_query:
            raise ValueError(f"Cannot build pinyin query for teacher name: {teacher_name}")

        return {
            "teacher_query": teacher_query,
            "cache_teacher_name": teacher_name,
            "should_warn_ascii_input": False,
        }

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
        max_candidates: int = 1,
    ) -> List[str]:
        seen = set()
        author_ids: List[str] = []
        query = self._build_query(teacher=teacher, school=school, school_aliases=school_aliases)
        logger.debug("Built single query for school=%s, teacher=%s: %s", school, teacher, query)

        google_url = f"https://www.google.com/search?q={quote(query)}&hl=en&num=10&start=0"
        logger.debug("Requesting search page start=0 with URL=%s", google_url)
        response = self._request_with_retry(
            url=google_url,
            params={
                "render": "false",
                "country_code": "us",
            },
        )
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
    load_dotenv(dotenv_path=ROOT_DIR / ".env")
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
