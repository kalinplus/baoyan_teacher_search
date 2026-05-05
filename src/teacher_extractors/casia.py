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


def supports_casia_faculty(url: str) -> bool:
    return "ia.cas.cn" in url and "yjsjy/dsjj" in url


def extract_casia_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen_names: set[str] = set()

    for match in re.finditer(
        r'<a\s+href="(https?://people\.ucas\.(?:ac|edu)\.cn/[^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw_url = match.group(1).strip()
        inner_html = match.group(2)
        name = normalize_spaces(strip_html_tags(unescape(inner_html)))

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


def extract_casia_names(html: str) -> List[str]:
    profiles = extract_casia_profiles(html, "")
    return [p.name for p in profiles]


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="casia_faculty_table",
            matcher=supports_casia_faculty,
            extractor=extract_casia_names,
            profile_extractor=extract_casia_profiles,
        ),
    ]
