from __future__ import annotations

import json
from typing import List
from urllib.parse import urljoin

import requests

from teacher_list_models import Rule, TeacherProfile

SII_API_URL = "https://www.sii.edu.cn/_wp3services/generalQuery?queryObj=articles"

SII_RETURN_INFOS = json.dumps([
    {"field": "title", "name": "title"},
    {"field": "url", "name": "url"},
    {"field": "shortTitle", "name": "shortTitle"},
    {"field": "summary", "name": "summary"},
])

SII_PAYLOAD = {
    "siteId": "3",
    "columnId": "92",
    "pageIndex": "1",
    "rows": "999",
    "returnInfos": SII_RETURN_INFOS,
    "conditions": "[]",
    "reqModule": "1",
}


def supports_sii_teachers(url: str) -> bool:
    return "sii.edu.cn/xyds_92/list.htm" in url


def _fetch_sii_api(timeout: int = 30) -> list:
    resp = requests.post(
        SII_API_URL,
        data=SII_PAYLOAD,
        timeout=timeout,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def extract_sii_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    items = _fetch_sii_api()
    profiles: List[TeacherProfile] = []
    seen_names: set[str] = set()
    for item in items:
        name = item.get("title", "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        raw_url = item.get("url", "")
        profile_url = urljoin(source_url, raw_url) if raw_url else None
        summary = item.get("summary", "").strip()
        title_line = summary.split("\n")[0].strip() if summary else None
        interests = [item.get("shortTitle", "").strip()] if item.get("shortTitle") else []
        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=profile_url,
                email=None,
                interests=interests,
                title=title_line,
                source_url=source_url,
            )
        )
    return profiles


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="sii_teachers",
            matcher=supports_sii_teachers,
            extractor=lambda _html: [],
            profile_extractor=extract_sii_profiles,
        ),
    ]
