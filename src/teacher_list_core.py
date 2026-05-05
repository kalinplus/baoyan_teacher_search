from __future__ import annotations

from typing import Dict, List, Optional

import requests

from teacher_list_helpers import (
    clean_teacher_names,
    clean_teacher_profiles,
    extract_name_from_anchor_text,
    extract_teacher_profiles_auto,
    fetch_html_with_weak_ssl,
    profile_to_dict,
)
from teacher_list_models import Rule, SourceRecord, TeacherProfile


DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}


def fetch_html(url: str, timeout: int) -> str:
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        return fetch_html_with_weak_ssl(url, timeout=timeout, headers=DEFAULT_HEADERS)

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


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


def collect_teachers(record: SourceRecord, timeout: int, rules: List[Rule], logger) -> Dict[str, object]:
    logger.info("Collecting teachers for school=%s college=%s", record.school, record.college)
    html = fetch_html(record.url, timeout=timeout)

    rule = find_rule(record.url, rules)
    if rule:
        rule_candidates = collect_profiles_with_rule(rule, html, source_url=record.url)
        selected_profiles = clean_teacher_profiles(rule_candidates, source_url=record.url)
        selected_mode = f"fallback:{rule.name}"
    else:
        auto_profiles = extract_teacher_profiles_auto(html, source_url=record.url)
        selected_profiles = clean_teacher_profiles(auto_profiles, source_url=record.url)
        selected_mode = "auto"

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


__all__ = [
    "Rule",
    "SourceRecord",
    "TeacherProfile",
    "clean_teacher_names",
    "collect_teachers",
    "extract_name_from_anchor_text",
    "fetch_html",
]
