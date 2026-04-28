from __future__ import annotations

import re
from html import unescape
from typing import List
from urllib.parse import urljoin

from teacher_list_models import Rule, TeacherProfile


CHINESE_NAME_PATTERN = re.compile(r"^[一-鿿]{2,4}$")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _is_chinese_name(value: str) -> bool:
    return bool(CHINESE_NAME_PATTERN.fullmatch(value))


def supports_ruc_faculty(url: str) -> bool:
    return "ai.ruc.edu.cn/academicfaculty" in url


def extract_ruc_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen_names: set[str] = set()

    # Split by tutor card blocks to avoid matching navigation links
    blocks = re.split(r'<div class="tutor media', html, flags=re.IGNORECASE)[1:]

    for block in blocks:
        # Extract name and profile URL from the <h2><a> tag
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

        if not _is_chinese_name(name):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)

        profile_url = urljoin(source_url, raw_url) if raw_url else None

        # Extract description/interests from <p class="position">
        position_match = re.search(
            r'<p class="position"[^>]*>(.*?)</p>', block, flags=re.IGNORECASE | re.DOTALL
        )
        interests: List[str] = []
        if position_match:
            raw_position = _normalize_text(unescape(_strip_html_tags(position_match.group(1))))
            # Truncate very long descriptions; keep first sentence or first 120 chars
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
