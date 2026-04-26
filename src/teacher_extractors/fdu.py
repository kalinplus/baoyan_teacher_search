from __future__ import annotations

import json
import re
from typing import List
from urllib.parse import urljoin

import requests

from teacher_list_models import Rule, TeacherProfile

FDU_API_URL = "https://cs.fudan.edu.cn/_wp3services/generalQuery?queryObj=teacherHome"

FDU_RETURN_INFOS = json.dumps([
    {"field": "title", "name": "title"},
    {"field": "cnUrl", "name": "cnUrl"},
    {"field": "headerPic", "name": "headerPic"},
    {"field": "exField1", "name": "exField1"},
    {"field": "firstLetter", "name": "firstLetter"},
    {"field": "letter", "name": "letter"},
    {"field": "exField9", "name": "exField9"},
    {"field": "exField7", "name": "exField7"},
    {"field": "email", "name": "email"},
    {"field": "career", "name": "career"},
])

FDU_ORDERS = json.dumps([
    {"field": "letter", "type": "asc"},
])

FDU_PAYLOAD = {
    "siteId": "577",
    "pageIndex": "1",
    "rows": "999",
    "conditions": "[]",
    "orders": FDU_ORDERS,
    "returnInfos": FDU_RETURN_INFOS,
    "articleType": "1",
    "level": "1",
}

CHINESE_NAME_PATTERN = re.compile(r"^[一-鿿]{2,4}$")


def supports_fdu_teachers(url: str) -> bool:
    return "cs.fudan.edu.cn/53162/list.htm" in url


def _fetch_fdu_api(timeout: int = 30) -> list:
    resp = requests.post(
        FDU_API_URL,
        data=FDU_PAYLOAD,
        timeout=timeout,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def extract_fdu_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    items = _fetch_fdu_api()
    profiles: List[TeacherProfile] = []
    seen_names: set[str] = set()

    for item in items:
        name = item.get("title", "").strip()
        if not name or name in seen_names:
            continue
        if not CHINESE_NAME_PATTERN.fullmatch(name):
            continue
        seen_names.add(name)

        raw_url = item.get("cnUrl", "")
        profile_url = urljoin(source_url, raw_url) if raw_url else None

        email = item.get("email", "").strip() or None
        if email:
            email = email.lower()

        title = item.get("exField9", "").strip() or None

        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=profile_url,
                email=email,
                interests=[],
                title=title,
                source_url=source_url,
            )
        )

    return profiles


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="fdu_teachers",
            matcher=supports_fdu_teachers,
            extractor=lambda _html: [],
            profile_extractor=extract_fdu_profiles,
        ),
    ]
