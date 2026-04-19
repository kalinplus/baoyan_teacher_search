from __future__ import annotations

import re
from html import unescape
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from teacher_list_models import TeacherProfile


NAVIGATION_BLACKLIST = {
    "首页",
    "上页",
    "下页",
    "尾页",
    "学院",
    "学校",
    "通知",
    "新闻",
    "公告",
    "招生",
    "下载",
    "联系我们",
    "师资队伍",
}
CHINESE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,4}$")
ENGLISH_NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z'\-]{1,30}(?:\s+[A-Z][A-Za-z'\-]{1,30}){1,3}$")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
TITLE_PATTERN = re.compile(
    r"(讲席教授|助理教授|副教授|教授|副研究员|研究员|工程师|长聘副教授|长聘教授|院长助理|博士后)"
)
ANCHOR_PATTERN = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
INTEREST_SPLIT_PATTERN = re.compile(r"[、,，;；/|\\]+")
TITLE_SUFFIXES = (
    "讲席教授",
    "助理教授",
    "副教授",
    "教授",
    "副研究员",
    "研究员",
    "工程师",
    "院长助理",
)
NAME_NOISE_KEYWORDS = (
    "官网",
    "谷歌",
    "火狐",
    "院系",
    "概况",
    "简介",
    "寄语",
    "领导",
    "沿革",
    "新闻",
    "动态",
    "媒体",
    "队伍",
    "全职",
    "研究",
    "荣誉",
    "兼职",
    "博士后",
    "行政",
    "实验员",
    "本科",
    "培养",
    "招生",
    "中心",
    "师资",
    "科研",
    "科学",
    "组织",
    "架构",
    "课题组",
    "校园",
    "生活",
    "衣食住行",
    "活动",
    "公告",
    "名录",
    "特殊",
    "聘任",
    "教务",
    "教学",
    "概述",
    "合作",
    "方向",
    "支撑",
    "平台",
    "重大",
    "项目",
    "工作",
    "学生",
    "社团",
    "奖助",
    "申请",
    "程序",
    "资助",
    "信息",
    "大学",
    "公开",
    "招聘",
    "职员",
    "校友",
    "频道",
    "风采",
    "俱乐",
    "捐赠",
    "热点",
    "讲座",
    "预告",
    "委员会",
    "办公室",
    "分工会",
    "运行",
    "流动",
)
ENGLISH_NAME_NOISE_KEYWORDS = (
    "english",
    "home",
    "faculty",
    "directory",
    "news",
    "research",
    "contact",
    "login",
    "about",
    "overview",
    "program",
    "student",
    "career",
    "download",
    "policy",
    "global",
    "study",
    "office",
    "center",
    "school",
    "college",
    "university",
)
PROFILE_URL_PERSON_KEYWORDS = (
    "/faculty/",
    "/faculty-detail/",
    "/teacher/",
    "/teachers/",
    "/people/",
    "/person/",
    "/staff/",
    "/profile/",
    "/professor/",
)


def normalize_text(value: str) -> str:
    return value.strip()


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def is_name_noise(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if normalized in NAVIGATION_BLACKLIST:
        return True
    if any(keyword in normalized for keyword in NAME_NOISE_KEYWORDS):
        return True

    lowered = normalized.lower()
    if any(keyword in lowered for keyword in ENGLISH_NAME_NOISE_KEYWORDS):
        return True
    return False


def is_teacher_name(value: str) -> bool:
    return bool(CHINESE_NAME_PATTERN.fullmatch(value) or ENGLISH_NAME_PATTERN.fullmatch(value))


def absolutize_url(raw_url: str, base_url: str) -> Optional[str]:
    url_value = normalize_text(raw_url)
    if not url_value or url_value.startswith("#"):
        return None
    if url_value.lower().startswith("javascript:"):
        return None

    joined = urljoin(base_url, url_value)
    parsed = urlparse(joined)
    if parsed.scheme not in {"http", "https"}:
        return None
    return urlunparse(parsed._replace(fragment=""))


def extract_title(text: str) -> Optional[str]:
    match = TITLE_PATTERN.search(text)
    if not match:
        return None
    return normalize_text(match.group(1))


def extract_emails(text: str) -> List[str]:
    return [item.lower() for item in EMAIL_PATTERN.findall(text)]


def looks_like_interest_text(text: str, name: str, title: Optional[str]) -> bool:
    if not text or text == name or (title and text == title):
        return False
    if len(text) < 4 or len(text) > 120:
        return False

    domain_keywords = (
        "智能",
        "学习",
        "视觉",
        "计算",
        "网络",
        "系统",
        "算法",
        "数据",
        "机器人",
        "语言",
        "通信",
        "安全",
        "优化",
        "芯片",
        "控制",
        "感知",
        "Research",
    )
    return any(keyword in text for keyword in domain_keywords)


def extract_interests(inner_html: str, context_text: str, name: str, title: Optional[str]) -> List[str]:
    raw_candidates: List[str] = []

    heading_candidates = re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", inner_html, flags=re.IGNORECASE | re.DOTALL)
    for raw in heading_candidates:
        candidate = normalize_spaces(strip_html_tags(unescape(raw)))
        if looks_like_interest_text(candidate, name=name, title=title):
            raw_candidates.append(candidate)

    keyword_candidates = re.findall(
        r"(?:研究方向|研究领域|Research\s*Interests?)\s*[:：]?\s*([^\n\r]{2,120})",
        context_text,
        flags=re.IGNORECASE,
    )
    raw_candidates.extend([normalize_spaces(item) for item in keyword_candidates])

    interests: List[str] = []
    seen = set()
    for candidate in raw_candidates:
        for chunk in INTEREST_SPLIT_PATTERN.split(candidate):
            value = normalize_text(chunk)
            if not value or value in seen:
                continue
            if len(value) < 2 or len(value) > 30:
                continue
            if not looks_like_interest_text(value, name=name, title=title):
                continue
            seen.add(value)
            interests.append(value)

    return interests


def extract_name_from_anchor_text(text: str) -> Optional[str]:
    def normalize_name_candidate(candidate: str) -> str:
        cleaned = re.sub(r"\s+", "", candidate)
        for suffix in TITLE_SUFFIXES:
            if cleaned.endswith(suffix):
                trimmed = cleaned[: -len(suffix)]
                if 2 <= len(trimmed) <= 4:
                    return trimmed
        return cleaned

    compact = normalize_name_candidate(text)
    if CHINESE_NAME_PATTERN.fullmatch(compact) and not is_name_noise(compact):
        return compact

    head_token = normalize_text(re.split(r"[\s|/，,;；]+", text)[0])
    head_token = re.sub(r"[（(].*?[）)]", "", head_token)
    head_token = normalize_name_candidate(head_token)
    if CHINESE_NAME_PATTERN.fullmatch(head_token) and not is_name_noise(head_token):
        return head_token

    english_candidate = normalize_spaces(re.sub(r"[（(].*?[）)]", "", text))
    if ENGLISH_NAME_PATTERN.fullmatch(english_candidate) and not is_name_noise(english_candidate):
        return english_candidate

    return None


def profile_richness(profile: TeacherProfile) -> int:
    return int(bool(profile.profile_url)) + int(bool(profile.email)) + int(bool(profile.title)) + len(profile.interests)


def merge_profiles(left: TeacherProfile, right: TeacherProfile) -> TeacherProfile:
    preferred, backup = (left, right) if profile_richness(left) >= profile_richness(right) else (right, left)
    merged_interests = list(dict.fromkeys([*preferred.interests, *backup.interests]))
    return TeacherProfile(
        name=preferred.name,
        profile_url=preferred.profile_url or backup.profile_url,
        email=preferred.email or backup.email,
        interests=merged_interests,
        title=preferred.title or backup.title,
        source_url=preferred.source_url or backup.source_url,
    )


def clean_teacher_profiles(candidates: Iterable[TeacherProfile], source_url: str) -> List[TeacherProfile]:
    deduped: Dict[str, TeacherProfile] = {}

    for candidate in candidates:
        normalized_name = re.sub(r"\s+", "", candidate.name)
        if ENGLISH_NAME_PATTERN.fullmatch(normalize_spaces(candidate.name)):
            normalized_name = normalize_spaces(candidate.name)
        if not normalized_name:
            continue
        if is_name_noise(normalized_name):
            continue
        if not is_teacher_name(normalized_name):
            continue

        normalized_profile = TeacherProfile(
            name=normalized_name,
            profile_url=absolutize_url(candidate.profile_url or "", source_url),
            email=(normalize_text(candidate.email).lower() if candidate.email else None),
            interests=list(dict.fromkeys([normalize_text(item) for item in candidate.interests if normalize_text(item)])),
            title=normalize_text(candidate.title) if candidate.title else None,
            source_url=normalize_text(candidate.source_url) or source_url,
        )

        existing = deduped.get(normalized_name)
        if not existing:
            deduped[normalized_name] = normalized_profile
            continue
        deduped[normalized_name] = merge_profiles(existing, normalized_profile)

    return list(deduped.values())


def profile_to_dict(profile: TeacherProfile) -> Dict[str, object]:
    return {
        "name": profile.name,
        "profile_url": profile.profile_url,
        "email": profile.email,
        "interests": list(profile.interests),
        "title": profile.title,
        "source_url": profile.source_url,
    }


def extract_teacher_profiles_auto(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    for match in ANCHOR_PATTERN.finditer(html):
        href = match.group(1)
        inner_html = match.group(2)
        profile_url = absolutize_url(href, source_url)
        if not profile_url:
            continue

        inner_text = normalize_spaces(strip_html_tags(unescape(inner_html)))
        name = extract_name_from_anchor_text(inner_text)
        if not name:
            continue

        context_start = max(0, match.start() - 600)
        context_end = min(len(html), match.end() + 600)
        context_html = html[context_start:context_end]
        context_text = normalize_spaces(strip_html_tags(unescape(context_html)))
        merged_text = f"{inner_text} {context_text}"

        emails = extract_emails(merged_text)
        email = emails[0] if emails else None
        title = extract_title(merged_text)
        interests = extract_interests(inner_html, merged_text, name=name, title=title)

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

    return profiles


def clean_teacher_names(candidates: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()

    for candidate in candidates:
        normalized = re.sub(r"\s+", "", candidate.strip())
        if not normalized:
            continue
        if is_name_noise(normalized):
            continue
        if not CHINESE_NAME_PATTERN.fullmatch(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def looks_like_profile_url(profile_url: Optional[str]) -> bool:
    if not profile_url:
        return False

    lowered = profile_url.lower()
    if "~" in lowered:
        return True
    return any(keyword in lowered for keyword in PROFILE_URL_PERSON_KEYWORDS)


def profile_quality(profiles: List[TeacherProfile]) -> float:
    if not profiles:
        return 0.0

    total = len(profiles)
    with_url = sum(1 for item in profiles if item.profile_url)
    with_rich = sum(1 for item in profiles if item.email or item.interests or item.title)
    with_person_url = sum(1 for item in profiles if looks_like_profile_url(item.profile_url))
    return 0.5 * (with_url / total) + 0.2 * (with_rich / total) + 0.3 * (with_person_url / total)


def should_use_fallback(auto_profiles: List[TeacherProfile], fallback_profiles: List[TeacherProfile]) -> bool:
    if not fallback_profiles:
        return False
    if not auto_profiles:
        return True

    auto_quality = profile_quality(auto_profiles)
    fallback_quality = profile_quality(fallback_profiles)
    if fallback_quality > auto_quality:
        return True

    if len(fallback_profiles) > len(auto_profiles):
        return True

    auto_richness = sum(profile_richness(item) for item in auto_profiles)
    fallback_richness = sum(profile_richness(item) for item in fallback_profiles)
    return fallback_richness > auto_richness
