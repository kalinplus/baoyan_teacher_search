from __future__ import annotations

import json
from typing import List
from urllib.parse import urlencode

from teacher_list_helpers import (
    CHINESE_NAME_PATTERN,
    INTEREST_SPLIT_PATTERN,
    absolutize_url,
    create_weak_ssl_pool_manager,
    normalize_spaces,
)
from teacher_list_models import Rule, TeacherProfile

NJU_API_URL = "https://is.nju.edu.cn/_wp3services/generalQuery?queryObj=teacherHome"
NJU_SITE_ID = "786"

NJU_RETURN_INFOS = json.dumps([
    {"field": "title", "name": "title"},
    {"field": "cnUrl", "name": "cnUrl"},
    {"field": "headerPic", "name": "headerPic"},
    {"field": "exField1", "name": "exField1"},
    {"field": "exField2", "name": "exField2"},
])

NJU_ORDERS = json.dumps([
    {"field": "siteSort", "type": "asc"},
])

NJU_TEACHER_CATEGORIES = [
    "教授",
    "副教授",
    "长聘副教授",
    "准聘副教授",
    "准聘助理教授",
    "兼职教授",
]

NJU_CONDITIONS = json.dumps([
    {"field": "published", "value": "1", "judge": "="},
    {"orConditions": [
        {"field": "exField2", "value": cat, "judge": "="}
        for cat in NJU_TEACHER_CATEGORIES
    ]},
])

NJU_PAYLOAD = {
    "siteId": NJU_SITE_ID,
    "pageIndex": "1",
    "rows": "999",
    "conditions": NJU_CONDITIONS,
    "orders": NJU_ORDERS,
    "returnInfos": NJU_RETURN_INFOS,
    "articleType": "1",
    "level": "1",
}

_NJU_HTTP = create_weak_ssl_pool_manager()


def supports_nju_is(url: str) -> bool:
    return "is.nju.edu.cn/57159/list.htm" in url


def _fetch_nju_api(timeout: int = 30) -> list:
    resp = _NJU_HTTP.request(
        "POST",
        NJU_API_URL,
        body=urlencode(NJU_PAYLOAD).encode("utf-8"),
        timeout=timeout,
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
    )
    return json.loads(resp.data.decode("utf-8")).get("data", [])


def _split_interests(value: str) -> List[str]:
    interests: List[str] = []
    seen: set[str] = set()
    for chunk in INTEREST_SPLIT_PATTERN.split(value):
        item = normalize_spaces(chunk)
        if not item or item in seen:
            continue
        if len(item) < 2 or len(item) > 40:
            continue
        seen.add(item)
        interests.append(item)
    return interests


def extract_nju_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    items = _fetch_nju_api()
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
        profile_url = absolutize_url(raw_url, source_url)

        title = item.get("exField2", "").strip() or None
        interests_raw = item.get("exField1", "").strip()
        interests = _split_interests(interests_raw) if interests_raw else []

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


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="nju_is_faculty",
            matcher=supports_nju_is,
            extractor=lambda _html: [],
            profile_extractor=extract_nju_profiles,
        ),
    ]
