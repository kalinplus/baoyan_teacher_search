from __future__ import annotations

import json
import re
from typing import List
from urllib.parse import urlencode, urljoin

import ssl
import urllib3

from teacher_list_models import Rule, TeacherProfile

NJU_API_URL = "https://is.nju.edu.cn/_wp3services/generalQuery?queryObj=teacherHome"
NJU_SITE_ID = "786"


def _create_nju_http() -> urllib3.PoolManager:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("ALL:@SECLEVEL=0")
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    return urllib3.PoolManager(ssl_context=ctx)


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

CHINESE_NAME_PATTERN = re.compile(r"^[一-鿿]{2,4}$")
INTEREST_SPLIT_PATTERN = re.compile(r"[、,，;；/|\\]+")


def supports_nju_is(url: str) -> bool:
    return "is.nju.edu.cn/57159/list.htm" in url


def _fetch_nju_api(timeout: int = 30) -> list:
    http = _create_nju_http()
    resp = http.request(
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
        item = re.sub(r"\s+", " ", chunk).strip()
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
        profile_url = urljoin(source_url, raw_url) if raw_url else None

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
