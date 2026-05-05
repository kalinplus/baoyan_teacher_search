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


def supports_ruc_faculty(url: str) -> bool:
    return "ai.ruc.edu.cn/academicfaculty" in url


def extract_ruc_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen_names: set[str] = set()

    blocks = re.split(r'<div class="tutor media', html, flags=re.IGNORECASE)[1:]

    for block in blocks:
        h2_match = re.search(
            r'<h2[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>\s*<small[^>]*>([^<]*)</small>\s*</h2>',
            block,
            flags=re.IGNORECASE,
        )
        if not h2_match:
            continue

        raw_url = h2_match.group(1).strip()
        name = h2_match.group(2).strip()
        title = h2_match.group(3).strip() or None

        if not CHINESE_NAME_PATTERN.fullmatch(name):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)

        profile_url = absolutize_url(raw_url, source_url)

        position_match = re.search(
            r'<p class="position"[^>]*>(.*?)</p>', block, flags=re.IGNORECASE | re.DOTALL
        )
        interests: List[str] = []
        if position_match:
            raw_position = normalize_spaces(unescape(strip_html_tags(position_match.group(1))))
            if len(raw_position) > 120:
                raw_position = raw_position[:120] + "..."
            if raw_position:
                interests = [raw_position]

        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=profile_url,
                email=None,
                interests=interests,
                title=title,
                source_url=source_url,
            )
        )

    return profiles


def extract_ruc_names(html: str) -> List[str]:
    profiles = extract_ruc_profiles(html, "")
    return [p.name for p in profiles]


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="ruc_faculty_tutor_card",
            matcher=supports_ruc_faculty,
            extractor=extract_ruc_names,
            profile_extractor=extract_ruc_profiles,
        ),
    ]
