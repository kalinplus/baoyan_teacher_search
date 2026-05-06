from __future__ import annotations

import re
from html import unescape
from typing import List

from teacher_list_helpers import (
    CHINESE_NAME_PATTERN,
    absolutize_url,
    normalize_spaces,
    strip_html_tags,
)
from teacher_list_models import Rule, TeacherProfile


def supports_ict_faculty(url: str) -> bool:
    return "ict.cas.cn" in url and "yjsjy/dsjj" in url


def extract_ict_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen_names: set[str] = set()

    # Match all teacher links under sourcedb/cn/jssrck (avatar list pattern)
    for match in re.finditer(
        r'<a\s+[^>]*href="([^"]*sourcedb/cn/jssrck/[^"]+)"[^>]*>([^<]+)</a>',
        html,
        flags=re.IGNORECASE,
    ):
        raw_url = match.group(1).strip()
        name = normalize_spaces(strip_html_tags(unescape(match.group(2))))

        if not CHINESE_NAME_PATTERN.fullmatch(name):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)

        profile_url = absolutize_url(raw_url, source_url)

        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=profile_url,
                email=None,
                interests=[],
                title=None,
                source_url=source_url,
            )
        )

    return profiles


def extract_ict_names(html: str) -> List[str]:
    profiles = extract_ict_profiles(html, "")
    return [p.name for p in profiles]


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="ict_faculty_avatar",
            matcher=supports_ict_faculty,
            extractor=extract_ict_names,
            profile_extractor=extract_ict_profiles,
        ),
    ]
