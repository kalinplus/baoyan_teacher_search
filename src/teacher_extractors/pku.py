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


def extract_pku_se_names(html: str) -> List[str]:
    profiles = extract_pku_se_profiles(html, "")
    return [p.name for p in profiles]


def extract_pku_se_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    blocks = re.split(r'<table class="fedd"[^>]*>', html, flags=re.IGNORECASE)[1:]

    for block in blocks:
        table_end = block.find('</table>')
        if table_end != -1:
            block = block[:table_end]

        name_match = re.search(r'<strong[^>]*>([^<]+)</strong>', block, flags=re.IGNORECASE)
        if not name_match:
            continue

        name = normalize_text(unescape(name_match.group(1)))
        if not is_chinese_name(name):
            continue

        # title is usually the first <td align="left"> after the name row
        title = None
        title_match = re.search(r'<td[^>]*align=["\']left["\'][^>]*>([^<]+)</td>', block, flags=re.IGNORECASE)
        if title_match:
            raw_title = normalize_text(unescape(title_match.group(1)))
            # skip degree lines like "2004年获得理学博士学位（北京大学）"
            if raw_title and not re.match(r"^\d{4}年", raw_title) and "获得" not in raw_title:
                title = raw_title

        # filter out contact-info mistakenly captured as title
        if title and any(k in title for k in ("E-mail", "办公地址", "联系电话", "Webpage")):
            title = None

        email_match = re.search(r'E-\s*mail\s*[：:]\s*([^\s<]+)', block, flags=re.IGNORECASE)
        email = email_match.group(1).strip() if email_match else None

        interests: List[str] = []
        interests_match = re.search(r'主要研究领域\s*[：:]\s*</strong>\s*([^<\n]+)', block, flags=re.IGNORECASE)
        if interests_match:
            raw = normalize_text(unescape(interests_match.group(1)))
            interests = [part.strip() for part in re.split(r"[、,，;；/|]+", raw) if part.strip()]

        profile_url = None
        webpage_match = re.search(r'Webpage\s*[：:]\s*(http[s]?://[^\s<]+)', block, flags=re.IGNORECASE)
        if webpage_match:
            profile_url = webpage_match.group(1).strip()

        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=profile_url,
                email=email,
                interests=interests,
                title=title,
                source_url=source_url,
            )
        )

    # Deduplicate by name, preferring the richer record (more fields filled)
    seen: dict[str, TeacherProfile] = {}
    for p in profiles:
        if p.name not in seen:
            seen[p.name] = p
        else:
            existing = seen[p.name]
            # richer = more non-null fields among email, interests, title
            existing_score = sum(bool(v) for v in [existing.email, existing.interests, existing.title])
            new_score = sum(bool(v) for v in [p.email, p.interests, p.title])
            if new_score > existing_score:
                seen[p.name] = p

    return list(seen.values())


def supports_pku_se(url: str) -> bool:
    return "se.pku.edu.cn/ky/kyry/index.htm" in url


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
        Rule(
            name="pku_se_table",
            matcher=supports_pku_se,
            extractor=extract_pku_se_names,
            profile_extractor=extract_pku_se_profiles,
        ),
    ]
