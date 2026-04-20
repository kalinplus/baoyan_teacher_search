from __future__ import annotations

import re
from html import unescape
from typing import List
from urllib.parse import urljoin

from teacher_list_models import Rule, TeacherProfile


CHINESE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,4}$")
AI_CENTER_KEYWORDS = (
    "计算机视觉",
    "自然语言处理",
    "多智能体",
    "具身智能",
    "机器人",
    "计算认知",
    "常识推理",
    "机器学习",
    "智能科学",
    "人工智能芯片",
    "大数据智能",
    "大模型",
    "人工智能安全",
    "人工智能治理",
)


def strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_chinese_name(value: str) -> bool:
    return bool(CHINESE_NAME_PATTERN.fullmatch(value))


def _is_ai_related_center(center_name: str) -> bool:
    return any(kw in center_name for kw in AI_CENTER_KEYWORDS)


import requests


def _extract_pku_cs_page_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    li_blocks = re.split(r"<li[^>]*>", html, flags=re.IGNORECASE)[1:]
    for block in li_blocks:
        name_match = re.search(r"<big>([^<]+)</big>", block, flags=re.IGNORECASE)
        if not name_match:
            continue

        name = name_match.group(1).strip()
        if not is_chinese_name(name):
            continue

        # Extract profile link from the wrapping <a> tag inside <li>
        href_match = re.search(r'<a\s+href="([^"]+)"[^>]*class="a"', block, flags=re.IGNORECASE)
        profile_url = urljoin(source_url, href_match.group(1)) if href_match else None

        title_match = re.search(r"<p[^>]*>\s*职称\s*[:：]\s*([^<]+)</p>", block, flags=re.IGNORECASE)
        title = normalize_text(unescape(title_match.group(1))) if title_match else None

        field_match = re.search(r"<p[^>]*>\s*研究领域\s*[:：]\s*([^<]+)</p>", block, flags=re.IGNORECASE)
        interests = []
        if field_match:
            raw = normalize_text(unescape(field_match.group(1)))
            interests = [part.strip() for part in re.split(r"[、,，;；/|]+", raw) if part.strip()]

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


def extract_pku_cs_names(html: str) -> List[str]:
    candidates = re.findall(r"<h3[^>]*><big>([^<]+)</big>", html, flags=re.IGNORECASE)
    return [name.strip() for name in candidates if is_chinese_name(name.strip())]


def extract_pku_cs_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles = _extract_pku_cs_page_profiles(html, source_url)

    base = source_url.rsplit("/", 1)[0] + "/"
    for i in range(1, 20):
        page_url = f"{base}ALL/{i}.htm"
        try:
            resp = requests.get(page_url, timeout=30)
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding
            page_profiles = _extract_pku_cs_page_profiles(resp.text, source_url)
            if not page_profiles:
                break
            profiles.extend(page_profiles)
        except requests.HTTPError as exc:
            if exc.response.status_code == 404:
                break
            raise

    seen: set[str] = set()
    deduped: List[TeacherProfile] = []
    for p in profiles:
        if p.name not in seen:
            seen.add(p.name)
            deduped.append(p)
    return deduped


def extract_pku_ai_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen_names = set()

    # Split by research center heading
    blocks = re.split(r"<h1\s+class=[\"']zzjs1M2h1[\"'][^>]*>", html, flags=re.IGNORECASE)
    for block in blocks[1:]:
        center_part, _, rest = block.partition("</h1>")
        center_name = normalize_text(strip_html_tags(unescape(center_part)))
        if not center_name or not _is_ai_related_center(center_name):
            continue

        links = re.findall(
            r"<P[^>]*id=[\"']\d+[\"'][^>]*>\s*<A\s+href=[\"']([^\"]+)[\"'][^>]*>([^<]+)</a>\s*</P>",
            rest,
            flags=re.IGNORECASE,
        )
        for href, raw_name in links:
            name = raw_name.strip()
            if "（" in name:
                name = name.split("（")[0].strip()
            if not is_chinese_name(name):
                continue
            if name in seen_names:
                continue
            seen_names.add(name)

            profile_url = urljoin(source_url, href)

            profiles.append(
                TeacherProfile(
                    name=name,
                    profile_url=profile_url,
                    email=None,
                    interests=[center_name] if center_name else [],
                    title=None,
                    source_url=source_url,
                )
            )

    return profiles


def supports_pku_cs(url: str) -> bool:
    return url.startswith("https://cs.pku.edu.cn/szdw/jyxl/amz/ALL.htm")


def supports_pku_ai(url: str) -> bool:
    return url.startswith("https://www.ai.pku.edu.cn/sztd/zzjyry1.htm")


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="pku_cs_h3big",
            matcher=supports_pku_cs,
            extractor=extract_pku_cs_names,
            profile_extractor=extract_pku_cs_profiles,
        ),
        Rule(
            name="pku_ai_center_anchor",
            matcher=supports_pku_ai,
            extractor=lambda _html: [],
            profile_extractor=extract_pku_ai_profiles,
        ),
    ]
