from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from scholar.author_id_resolver import AuthorIdResolver, UNIVERSITY_CONFIG_PATH, load_university_mapping, normalize_school_name


SKIP_REASON_AUTHOR_ID_CONFLICT = "author_id_conflict_existing_teacher"
SKIP_REASON_SCHOLAR_NAME_MISMATCH = "scholar_name_mismatch"


def _extract_skip_reason(error_message: str) -> Optional[str]:
    if f"skip_reason={SKIP_REASON_AUTHOR_ID_CONFLICT}" in error_message:
        return SKIP_REASON_AUTHOR_ID_CONFLICT
    if f"skip_reason={SKIP_REASON_SCHOLAR_NAME_MISMATCH}" in error_message:
        return SKIP_REASON_SCHOLAR_NAME_MISMATCH
    return None


def resolve_teacher_author_id(
    *,
    school: str,
    teacher: str,
    cache_path: Path,
    timeout: int,
    school_aliases: Optional[List[str]] = None,
) -> Dict[str, Any]:
    university_mapping = load_university_mapping(UNIVERSITY_CONFIG_PATH)
    canonical_school = normalize_school_name(school, university_mapping)

    scraperapi_key = os.getenv("SCRAPERAPI_KEY", "").strip()
    resolver = AuthorIdResolver(scraperapi_key=scraperapi_key, timeout=timeout)

    try:
        resolved = resolver.resolve(
            school=canonical_school,
            teacher=teacher,
            cache_path=cache_path,
            school_aliases=school_aliases if school_aliases is not None else university_mapping.get(canonical_school, []),
        )
    except RuntimeError as exc:
        skip_reason = _extract_skip_reason(str(exc))
        if not skip_reason:
            raise
        return {
            "teacher": teacher,
            "status": "skip",
            "skip_reason": skip_reason,
            "author_id": None,
            "author_id_source": None,
            "matched_school": canonical_school,
            "matched_teacher": teacher,
            "error": str(exc),
        }

    return {
        "teacher": teacher,
        "status": "resolved",
        "skip_reason": None,
        "author_id": resolved["author_id"],
        "author_id_source": resolved["source"],
        "matched_school": resolved["matched_school"],
        "matched_teacher": resolved["matched_teacher"],
        "error": None,
    }
