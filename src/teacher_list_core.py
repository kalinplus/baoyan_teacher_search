from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests


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
PROFILE_URL_PERSON_KEYWORDS = (
    "/faculty/",
    "/teacher/",
    "/teachers/",
    "/people/",
    "/person/",
    "/staff/",
    "/profile/",
    "/professor/",
)


@dataclass(frozen=True)
class TeacherProfile:
    name: str
    profile_url: Optional[str]
    email: Optional[str]
    interests: List[str] = field(default_factory=list)
    title: Optional[str] = None
    source_url: str = ""


@dataclass(frozen=True)
class SourceRecord:
    school: str
    college: str
    url: str


@dataclass(frozen=True)
class Rule:
    name: str
    matcher: Callable[[str], bool]
    extractor: Callable[[str], List[str]]
    profile_extractor: Optional[Callable[[str, str], List[TeacherProfile]]] = None


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
    return any(keyword in normalized for keyword in NAME_NOISE_KEYWORDS)


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
        if not normalized_name:
            continue
        if is_name_noise(normalized_name):
            continue
        if not CHINESE_NAME_PATTERN.fullmatch(normalized_name):
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


def load_source_records(path: Path) -> List[SourceRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Input source file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input source file must be a JSON array")

    records: List[SourceRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Source record at index {index} must be an object")

        school = normalize_text(str(item.get("school", "")))
        college = normalize_text(str(item.get("college", "")))
        url = normalize_text(str(item.get("url", "")))
        if not school or not college or not url:
            raise ValueError(f"Source record at index {index} missing required fields")

        records.append(SourceRecord(school=school, college=college, url=url))

    return records


def fetch_html(url: str, timeout: int) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


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


def validate_teacher_profiles(profiles: List[TeacherProfile], record: SourceRecord) -> None:
    if not profiles:
        raise RuntimeError(f"No teachers extracted for {record.school} / {record.college}")

    names = [profile.name for profile in profiles]
    if len(names) != len(set(names)):
        raise RuntimeError(f"Duplicate names detected after cleaning for {record.school} / {record.college}")


def find_rule(url: str, rules: List[Rule]) -> Optional[Rule]:
    for rule in rules:
        if rule.matcher(url):
            return rule
    return None


def collect_profiles_with_rule(rule: Rule, html: str, source_url: str) -> List[TeacherProfile]:
    if rule.profile_extractor:
        return rule.profile_extractor(html, source_url)

    names = rule.extractor(html)
    return [
        TeacherProfile(
            name=name,
            profile_url=None,
            email=None,
            interests=[],
            title=None,
            source_url=source_url,
        )
        for name in names
    ]


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


def collect_teachers(record: SourceRecord, timeout: int, rules: List[Rule], logger) -> Dict[str, object]:
    logger.info("Collecting teachers for school=%s college=%s", record.school, record.college)
    html = fetch_html(record.url, timeout=timeout)

    auto_profiles = clean_teacher_profiles(extract_teacher_profiles_auto(html, source_url=record.url), source_url=record.url)
    selected_profiles = auto_profiles
    selected_mode = "auto"

    rule = find_rule(record.url, rules)
    if rule:
        fallback_candidates = collect_profiles_with_rule(rule, html, source_url=record.url)
        fallback_profiles = clean_teacher_profiles(fallback_candidates, source_url=record.url)
        if should_use_fallback(auto_profiles, fallback_profiles):
            selected_profiles = fallback_profiles
            selected_mode = f"fallback:{rule.name}"

    validate_teacher_profiles(selected_profiles, record)
    teachers = [profile.name for profile in selected_profiles]
    teacher_profiles = [profile_to_dict(profile) for profile in selected_profiles]

    logger.info("Extraction done mode=%s, teacher_count=%s", selected_mode, len(teachers))
    return {
        "school": record.school,
        "college": record.college,
        "url": record.url,
        "teachers": teachers,
        "teacher_profiles": teacher_profiles,
    }


def save_result(out_dir: Path, payload: Dict[str, object]) -> Path:
    school = str(payload["school"])
    college = str(payload["college"])
    target_dir = out_dir / school / college
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / "teachers.json"
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def export_jsonl(path: Path, results: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []

    for result in results:
        school = str(result["school"])
        college = str(result["college"])
        url = str(result["url"])
        profile_map = {
            str(item.get("name", "")): item
            for item in result.get("teacher_profiles", [])
            if isinstance(item, dict)
        }

        for teacher in result["teachers"]:
            profile = profile_map.get(str(teacher), {})
            lines.append(
                json.dumps(
                    {
                        "school": school,
                        "college": college,
                        "teacher": teacher,
                        "url": url,
                        "profile_url": profile.get("profile_url"),
                        "email": profile.get("email"),
                        "interests": profile.get("interests", []),
                        "title": profile.get("title"),
                        "source_url": profile.get("source_url", url),
                    },
                    ensure_ascii=False,
                )
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_direct_record(school: str, college: str, url: str) -> SourceRecord:
    school_name = normalize_text(school)
    college_name = normalize_text(college)
    url_value = normalize_text(url)
    if not school_name or not college_name or not url_value:
        raise ValueError("Direct mode requires non-empty --school --college --url")
    return SourceRecord(school=school_name, college=college_name, url=url_value)


def select_records(args: argparse.Namespace) -> List[SourceRecord]:
    if args.url:
        return [build_direct_record(args.school, args.college, args.url)]

    records = load_source_records(Path(args.input))
    if not args.school and not args.college:
        return records

    filtered = [
        item
        for item in records
        if (not args.school or item.school == normalize_text(args.school))
        and (not args.college or item.college == normalize_text(args.college))
    ]
    if not filtered:
        raise ValueError("No source record matched --school/--college filters")
    return filtered
