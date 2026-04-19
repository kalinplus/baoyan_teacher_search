from __future__ import annotations

import json
import re
from functools import lru_cache
from html import unescape
from pathlib import Path
from typing import List

import requests

from teacher_list_models import Rule, TeacherProfile


ROOT_DIR = Path(__file__).resolve().parents[2]
THU_SIGS_SUBJECT_KEYWORDS_PATH = ROOT_DIR / "config" / "sigs_subject_keywords.json"


@lru_cache(maxsize=1)
def load_thu_sigs_subject_keywords() -> tuple[str, ...]:
    if not THU_SIGS_SUBJECT_KEYWORDS_PATH.exists():
        raise FileNotFoundError(f"SIGS subject keywords config not found: {THU_SIGS_SUBJECT_KEYWORDS_PATH}")

    payload = json.loads(THU_SIGS_SUBJECT_KEYWORDS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("SIGS subject keywords config must be a JSON array")

    keywords: List[str] = []
    for item in payload:
        if not isinstance(item, str):
            raise ValueError(f"SIGS subject keyword must be string, got: {item!r}")
        keyword = item.strip()
        if not keyword:
            raise ValueError("SIGS subject keyword cannot be empty")
        keywords.append(keyword)

    if not keywords:
        raise ValueError("SIGS subject keywords config cannot be empty")
    return tuple(keywords)


def strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def _extract_h4_names(section_html: str) -> List[str]:
    candidates = re.findall(r"<h4[^>]*>(.*?)</h4>", section_html, flags=re.IGNORECASE | re.DOTALL)
    return [strip_html_tags(unescape(name)).strip() for name in candidates]


def _find_anchor_start(html: str, anchor_name: str) -> int:
    pattern = re.compile(rf"<a\s+name=[\"']{re.escape(anchor_name)}[\"'][^>]*>", re.IGNORECASE)
    match = pattern.search(html)
    if not match:
        raise ValueError(f"Anchor not found: {anchor_name}")
    return match.start()


def _extract_between_anchors(html: str, start_anchor: str, end_anchor: str) -> str:
    start_index = _find_anchor_start(html, start_anchor)
    end_index = _find_anchor_start(html, end_anchor)
    if end_index <= start_index:
        raise ValueError(f"Invalid anchor order: {start_anchor} -> {end_anchor}")
    return html[start_index:end_index]


def _extract_between_keywords(html: str, start_keyword: str, end_keyword: str) -> str:
    start_match = re.search(re.escape(start_keyword), html)
    if not start_match:
        raise ValueError(f"Start keyword not found: {start_keyword}")

    end_match = re.search(re.escape(end_keyword), html[start_match.start() :])
    if not end_match:
        raise ValueError(f"End keyword not found: {end_keyword}")

    end_index = start_match.start() + end_match.start()
    if end_index <= start_match.start():
        raise ValueError(f"Invalid keyword order: {start_keyword} -> {end_keyword}")
    return html[start_match.start() : end_index]


def extract_thu_cs_h2_anchor_names(html: str) -> List[str]:
    pattern = re.compile(r"<h2>\s*<a[^>]*>(.*?)</a>\s*</h2>", re.IGNORECASE | re.DOTALL)
    candidates = pattern.findall(html)
    return [strip_html_tags(unescape(name)) for name in candidates]


def extract_thu_thss_faculty_names(html: str) -> List[str]:
    pattern = re.compile(r"<a[^>]*href=[\"']\.\./faculty/[^\"'#?]+\.htm[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
    candidates = pattern.findall(html)
    return [strip_html_tags(unescape(name)).strip() for name in candidates]


def extract_thu_thss_faculty_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    pattern = re.compile(
        r"<a[^>]*href=[\"'](\.\./faculty/[^\"'#?]+\.htm)[\"'][^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    profiles: List[TeacherProfile] = []
    for href, name_html in pattern.findall(html):
        name = strip_html_tags(unescape(name_html)).strip()
        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=href,
                email=None,
                interests=[],
                title=None,
                source_url=source_url,
            )
        )
    return profiles


def extract_thu_ai_fulltime_pi_names(html: str) -> List[str]:
    section = _extract_between_anchors(html, start_anchor="sz2", end_anchor="sz3")
    return _extract_h4_names(section)


def extract_thu_ai_fulltime_pi_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    section = _extract_between_anchors(html, start_anchor="sz2", end_anchor="sz3")
    pattern = re.compile(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
    profiles: List[TeacherProfile] = []

    for href, block_html in pattern.findall(section):
        headings = re.findall(r"<h4[^>]*>(.*?)</h4>", block_html, flags=re.IGNORECASE | re.DOTALL)
        if not headings:
            continue

        name = strip_html_tags(unescape(headings[0])).strip()
        title_match = re.search(r"<p[^>]*>(.*?)</p>", block_html, flags=re.IGNORECASE | re.DOTALL)
        title = strip_html_tags(unescape(title_match.group(1))).strip() if title_match else None

        interests_heading = re.search(
            r"<h4[^>]*class=[\"'][^\"']*h4s2[^\"']*[\"'][^>]*>(.*?)</h4>",
            block_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        interests_text = strip_html_tags(unescape(interests_heading.group(1))).strip() if interests_heading else ""
        interests = [part.strip() for part in re.split(r"[、,，;；/|]+", interests_text) if part.strip()]

        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", block_html)
        email = email_match.group(0).lower() if email_match else None

        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=href,
                email=email,
                interests=interests,
                title=title,
                source_url=source_url,
            )
        )

    return profiles


def extract_thu_iiis_fulltime_and_research_names(html: str) -> List[str]:
    section_fulltime = _extract_between_anchors(html, start_anchor="sz1", end_anchor="sz8")
    section_research = _extract_between_anchors(html, start_anchor="sz8", end_anchor="sz4")
    return [*_extract_h4_names(section_fulltime), *_extract_h4_names(section_research)]


def extract_thu_insc_names(html: str) -> List[str]:
    section = _extract_between_keywords(html, start_keyword="学术带头人", end_keyword="友情链接")
    candidates = re.findall(r"<a[^>]*href=[\"'][^\"']*\.htm[^\"']*[\"'][^>]*>(.*?)</a>", section, flags=re.IGNORECASE | re.DOTALL)
    return [strip_html_tags(unescape(name)).strip() for name in candidates]


def extract_thu_au_bdmd_names(html: str) -> List[str]:
    candidates = re.findall(r"<h4[^>]*class=[\"']h4s1[\"'][^>]*>(.*?)</h4>", html, flags=re.IGNORECASE | re.DOTALL)
    return [strip_html_tags(unescape(name)).strip() for name in candidates]


def extract_thu_ee_zh_names(html: str) -> List[str]:
    candidates = re.findall(r'"showTitle"\s*:\s*"([^"]+)"', html, flags=re.IGNORECASE)
    return [strip_html_tags(unescape(name)).strip() for name in candidates]


def _fetch_sigs_teacher_home_items() -> List[dict]:
    endpoint = "https://www.sigs.tsinghua.edu.cn/_wp3services/generalQuery?queryObj=teacherHome"
    conditions = [{"conditions": [{"field": "published", "value": "1", "judge": "="}]}]
    orders = [{"field": "firstLetter", "type": "asc"}]
    return_infos = [
        {"field": "title", "name": "title"},
        {"field": "headerPic", "name": "headerPic"},
        {"field": "career", "name": "career"},
        {"field": "cnUrl", "name": "cnUrl"},
        {"field": "enUrl", "name": "enUrl"},
        {"field": "phone", "name": "phone"},
        {"field": "email", "name": "email"},
        {"field": "fax", "name": "fax"},
        {"field": "exField1", "name": "exField1"},
        {"field": "exField2", "name": "exField2"},
        {"field": "exField3", "name": "exField3"},
        {"field": "exField4", "name": "exField4"},
        {"field": "exField5", "name": "exField5"},
        {"field": "exField7", "name": "exField7"},
        {"field": "exField8", "name": "exField8"},
        {"field": "exContent14", "name": "exContent14"},
    ]

    payload = {
        "siteId": "3",
        "articleType": "1",
        "level": "1",
        "pageIndex": "1",
        "rows": "999",
        "conditions": json.dumps(conditions, ensure_ascii=False),
        "orders": json.dumps(orders, ensure_ascii=False),
        "returnInfos": json.dumps(return_infos, ensure_ascii=False),
    }
    response = requests.post(endpoint, data=payload, timeout=30)
    response.raise_for_status()
    payload_obj = response.json()
    return payload_obj.get("data", [])


def extract_thu_sigs_cs_names(_html: str) -> List[str]:
    items = _fetch_sigs_teacher_home_items()
    keywords = load_thu_sigs_subject_keywords()
    targets: List[str] = []

    for item in items:
        subject = str(item.get("exField5", "")).strip()
        if any(keyword in subject for keyword in keywords):
            targets.append(str(item.get("title", "")))

    return targets


def supports_thu_cs(url: str) -> bool:
    return url.startswith("https://www.cs.tsinghua.edu.cn/szzk/jzgml.htm")


def supports_thu_thss(url: str) -> bool:
    return url.startswith("https://www.thss.tsinghua.edu.cn/szdw/jsml.htm")


def supports_thu_ai(url: str) -> bool:
    return url.startswith("https://collegeai.tsinghua.edu.cn/rydw.htm")


def supports_thu_iiis(url: str) -> bool:
    return url.startswith("https://iiis.tsinghua.edu.cn/rydw.htm")


def supports_thu_insc(url: str) -> bool:
    return url.startswith("https://www.insc.tsinghua.edu.cn/szdw_/jsml.htm")


def supports_thu_au_bdmd(url: str) -> bool:
    return url.startswith("https://www.au.tsinghua.edu.cn/zsjy/bdmd.htm")


def supports_thu_ee_zh(url: str) -> bool:
    return url.startswith("https://www.ee.tsinghua.edu.cn/ryqk/teacher/xxgdzyjs/js2.htm")


def supports_thu_sigs(url: str) -> bool:
    return url.startswith("https://www.sigs.tsinghua.edu.cn/7644/list.htm")


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="thu_cs_h2_anchor",
            matcher=supports_thu_cs,
            extractor=extract_thu_cs_h2_anchor_names,
        ),
        Rule(
            name="thu_thss_faculty_anchor",
            matcher=supports_thu_thss,
            extractor=extract_thu_thss_faculty_names,
            profile_extractor=extract_thu_thss_faculty_profiles,
        ),
        Rule(
            name="thu_ai_fulltime_pi_h4",
            matcher=supports_thu_ai,
            extractor=extract_thu_ai_fulltime_pi_names,
            profile_extractor=extract_thu_ai_fulltime_pi_profiles,
        ),
        Rule(
            name="thu_iiis_fulltime_research_h4",
            matcher=supports_thu_iiis,
            extractor=extract_thu_iiis_fulltime_and_research_names,
        ),
        Rule(
            name="thu_insc_a_anchor",
            matcher=supports_thu_insc,
            extractor=extract_thu_insc_names,
        ),
        Rule(
            name="thu_au_bdmd_h4s1",
            matcher=supports_thu_au_bdmd,
            extractor=extract_thu_au_bdmd_names,
        ),
        Rule(
            name="thu_ee_zh_showtitle",
            matcher=supports_thu_ee_zh,
            extractor=extract_thu_ee_zh_names,
        ),
        Rule(
            name="thu_sigs_cs_keyword",
            matcher=supports_thu_sigs,
            extractor=extract_thu_sigs_cs_names,
        ),
    ]
