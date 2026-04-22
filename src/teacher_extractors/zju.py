from __future__ import annotations

import re
from html import unescape
from typing import List

from teacher_list_models import Rule, TeacherProfile

CHINESE_NAME_PATTERN = re.compile(r"^[一-鿿]{2,4}$")

ZJU_CST_PATTERN = re.compile(
    r"""href=["']https://person\.zju\.edu\.cn/([^"']+)["'][^>]*title=["']([^"']+)["']""",
)

ZJU_CS_PATTERN = re.compile(
    r"""href=['"]https://person\.zju\.edu\.cn/([^'"]+)['"][^>]*title=['"]([^'"]+)['"]""",
)


def _normalize_name(raw: str) -> str:
    name = unescape(raw).strip().replace(" ", "").replace("　", "")
    return name


def extract_zju_cst_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen = set()
    for m in ZJU_CST_PATTERN.finditer(html):
        profile_id = m.group(1)
        name = _normalize_name(m.group(2))
        if not name or profile_id in seen:
            continue
        if not CHINESE_NAME_PATTERN.fullmatch(name):
            continue
        seen.add(profile_id)
        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=f"https://person.zju.edu.cn/{profile_id}",
                email=None,
                source_url=source_url,
            )
        )
    return profiles


def extract_zju_cs_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []
    seen = set()
    for m in ZJU_CS_PATTERN.finditer(html):
        profile_id = m.group(1)
        name = _normalize_name(m.group(2))
        if not name or profile_id in seen:
            continue
        if not CHINESE_NAME_PATTERN.fullmatch(name):
            continue
        seen.add(profile_id)
        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=f"https://person.zju.edu.cn/{profile_id}",
                email=None,
                source_url=source_url,
            )
        )
    return profiles


def supports_zju_cst(url: str) -> bool:
    return "cst.zju.edu.cn/szdw/list.htm" in url


def supports_zju_cs(url: str) -> bool:
    return "cs.zju.edu.cn/csen/27003/list.htm" in url


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="zju_cst_person",
            matcher=supports_zju_cst,
            extractor=lambda _html: [],
            profile_extractor=extract_zju_cst_profiles,
        ),
        Rule(
            name="zju_cs_person",
            matcher=supports_zju_cs,
            extractor=lambda _html: [],
            profile_extractor=extract_zju_cs_profiles,
        ),
    ]
