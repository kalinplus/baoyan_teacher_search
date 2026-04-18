from __future__ import annotations

import re
from html import unescape
from typing import List

import requests

from teacher_list_core import Rule, TeacherProfile


CHINESE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,4}$")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
TITLE_PATTERN = re.compile(r"(讲席教授|助理教授|副教授|教授|副研究员|研究员|工程师|长聘副教授|长聘教授|院长助理|博士后)")
INTEREST_SPLIT_PATTERN = re.compile(r"[、,，;；/|\\]+")
ANCHOR_PATTERN = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
SOAI_CARD_PATTERN = re.compile(
    r"<a[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*class=[\"'][^\"']*pd[^\"']*[\"'][^>]*>(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
SOAI_CARD_NAME_PATTERN = re.compile(
    r"<div[^>]*class=[\"'][^\"']*h3[^\"']*[\"'][^>]*>(?P<name>.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)

SOAI_DETAIL_URL_KEYWORDS = ("facultydetails", "teacherdetails", "teacherdetail")
SOAI_NAV_URL_KEYWORDS = (
    "/cn/article/",
    "/cn/news/",
    "/cn/list/",
    "/cn/down/",
    "/cn/faculty/zzjs",
    "/cn/teacher/spkz",
    "/cn/teacher/bsh",
    "/cn/login",
)

CSE_FALLBACK_URL = "https://cs.sjtu.edu.cn/cse/People.aspx?id=9"
SJTU_CS_AJAX_URL = "https://www.cs.sjtu.edu.cn/active/ajax_teacher_list.html"
SJTU_CS_AJAX_PAYLOAD = {
    "page": 1,
    "cat_id": "20",
    "cat_code": "jiaoshiml",
    "type": 1,
    "zm": "All",
    "zc": "全部",
    "search": "",
}
SJTU_CS_RC_ITEM_SPLIT_PATTERN = re.compile(
    r"<div\s+class=[\"']rc-item[\"']\s*>",
    flags=re.IGNORECASE,
)
SJTU_CS_INSTITUTE_PATTERN = re.compile(
    r"<div\s+class=[\"']name[\"']\s*>(?P<name>.*?)</div>",
    flags=re.IGNORECASE | re.DOTALL,
)
SJTU_CS_ANCHOR_PATTERN = re.compile(
    r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
SJTU_CS_HREF_ATTR_PATTERN = re.compile(
    r"href=[\"'](?P<href>[^\"']+)[\"']",
    flags=re.IGNORECASE,
)
SJTU_CS_SPAN_PATTERN = re.compile(
    r"<span\b[^>]*>(?P<body>.*?)</span>",
    flags=re.IGNORECASE | re.DOTALL,
)
CSE_LIST_ITEM_PATTERN = re.compile(
    r"<li>.*?<h2>\s*(?P<name>[\u4e00-\u9fff]{2,4})\s*</h2>.*?<p>\s*研究领域[:：]?\s*(?P<research>.*?)</p>.*?"
    r"<a[^>]*href=[\"'](?P<href>[^\"']*PeopleDetail\.aspx\?id=\d+)[\"'][^>]*>",
    flags=re.IGNORECASE | re.DOTALL,
)
GIFT_TEACHER_ANCHOR_PATTERN = re.compile(
    r"<a[^>]*href=[\"'](?P<href>[^\"']*/faculty/\d+)[\"'][^>]*>(?P<body>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
GC_TEACHER_ANCHOR_PATTERN = re.compile(
    r"<a[^>]*href=[\"'](?P<href>[^\"']*/faculty-detail/\d+)[\"'][^>]*>(?P<body>.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
ENGLISH_NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z'\-]{1,30}(?:\s+[A-Z][A-Za-z'\-]{1,30}){1,3}$")


def strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_chinese_name(value: str) -> bool:
    return bool(CHINESE_NAME_PATTERN.fullmatch(value))


def fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def fetch_sjtu_cs_ajax_content(timeout: int = 30) -> str:
    response = requests.post(SJTU_CS_AJAX_URL, data=SJTU_CS_AJAX_PAYLOAD, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    content = payload.get("content", "")
    if not isinstance(content, str):
        raise RuntimeError("SJTU CS AJAX content is not a string")
    return content


def extract_title(text: str) -> str | None:
    match = TITLE_PATTERN.search(text)
    if not match:
        return None
    return normalize_text(match.group(1))


def split_interests(value: str) -> List[str]:
    interests: List[str] = []
    seen = set()

    for chunk in INTEREST_SPLIT_PATTERN.split(value):
        item = normalize_text(chunk)
        if not item or item in seen:
            continue
        if len(item) < 2 or len(item) > 40:
            continue
        seen.add(item)
        interests.append(item)

    return interests


def extract_context_text(html: str, start: int, end: int, window: int = 220) -> str:
    context_start = max(0, start - window)
    context_end = min(len(html), end + window)
    return normalize_text(strip_html_tags(unescape(html[context_start:context_end])))


def looks_like_soai_detail_url(href: str) -> bool:
    lowered = href.lower()
    return any(keyword in lowered for keyword in SOAI_DETAIL_URL_KEYWORDS)


def is_soai_nav_url(href: str) -> bool:
    lowered = href.lower()
    return lowered.startswith("javascript:") or any(keyword in lowered for keyword in SOAI_NAV_URL_KEYWORDS)


def extract_soai_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    for match in SOAI_CARD_PATTERN.finditer(html):
        href = normalize_text(match.group("href"))
        if not href or href.startswith("#") or is_soai_nav_url(href):
            continue

        body_html = match.group("body")
        name_match = SOAI_CARD_NAME_PATTERN.search(body_html)
        if not name_match:
            continue

        name = normalize_text(strip_html_tags(unescape(name_match.group("name")))).replace(" ", "")
        if not is_chinese_name(name):
            continue

        context_text = normalize_text(strip_html_tags(unescape(body_html)))
        emails = EMAIL_PATTERN.findall(context_text)
        email = emails[0].lower() if emails else None
        title = extract_title(context_text)

        interests = []
        interests_match = re.search(
            r"(?:研究方向|研究领域|Research\s*Interests?)\s*[:：]?\s*([^\n\r]{2,120})",
            context_text,
            flags=re.IGNORECASE,
        )
        if interests_match:
            interests = split_interests(interests_match.group(1))

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

    for match in ANCHOR_PATTERN.finditer(html):
        href = normalize_text(match.group(1))
        if not href or href.startswith("#") or is_soai_nav_url(href):
            continue
        lowered_href = href.lower()
        if lowered_href.startswith("http") and "sjtu.edu.cn" not in lowered_href and not looks_like_soai_detail_url(href):
            continue

        name = normalize_text(strip_html_tags(unescape(match.group(2)))).replace(" ", "")
        if not is_chinese_name(name):
            continue

        context_text = extract_context_text(html, start=match.start(), end=match.end())
        emails = EMAIL_PATTERN.findall(context_text)
        email = emails[0].lower() if emails else None
        title = extract_title(context_text)

        interests = []
        interests_match = re.search(
            r"(?:研究方向|研究领域|Research\s*Interests?)\s*[:：]?\s*([^\n\r]{2,120})",
            context_text,
            flags=re.IGNORECASE,
        )
        if interests_match:
            interests = split_interests(interests_match.group(1))

        if not looks_like_soai_detail_url(href) and not lowered_href.startswith("/cn/show/") and not (email or title or interests):
            continue

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


def extract_sjtu_soai_zzjs_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    return extract_soai_profiles(html, source_url)


def extract_sjtu_soai_spkz_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    return extract_soai_profiles(html, source_url)


def extract_sjtu_cse_people_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    for match in CSE_LIST_ITEM_PATTERN.finditer(html):
        name = normalize_text(match.group("name"))
        if not is_chinese_name(name):
            continue

        research = normalize_text(strip_html_tags(unescape(match.group("research"))))
        if research.startswith("研究领域"):
            research = normalize_text(research.split("：", 1)[-1])

        profiles.append(
            TeacherProfile(
                name=name,
                profile_url=normalize_text(match.group("href")),
                email=None,
                interests=split_interests(research),
                title=None,
                source_url=source_url,
            )
        )

    return profiles


def extract_sjtu_cs_name_candidate(text: str) -> str | None:
    compact = normalize_text(text).replace("　", "")
    compact_no_space = re.sub(r"\s+", "", compact)
    if is_chinese_name(compact_no_space):
        return compact_no_space

    english = normalize_text(re.sub(r"\s+", " ", compact))
    if ENGLISH_NAME_PATTERN.fullmatch(english):
        return english
    return None


def extract_sjtu_cs_ajax_profiles(content_html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    blocks = SJTU_CS_RC_ITEM_SPLIT_PATTERN.split(content_html)
    for block_html in blocks[1:]:
        institute_match = SJTU_CS_INSTITUTE_PATTERN.search(block_html)
        institute = None
        if institute_match:
            institute_text = normalize_text(strip_html_tags(unescape(institute_match.group("name"))))
            institute = institute_text if institute_text else None

        for anchor_match in SJTU_CS_ANCHOR_PATTERN.finditer(block_html):
            attrs = anchor_match.group("attrs")
            href_match = SJTU_CS_HREF_ATTR_PATTERN.search(attrs)
            href = normalize_text(href_match.group("href")) if href_match else None

            name_text = normalize_text(strip_html_tags(unescape(anchor_match.group("body"))))
            name = extract_sjtu_cs_name_candidate(name_text)
            if not name:
                continue

            if href and "/jiaoshiml/" not in href:
                continue

            interests = [institute] if institute else []
            profiles.append(
                TeacherProfile(
                    name=name,
                    profile_url=href,
                    email=None,
                    interests=interests,
                    title=None,
                    source_url=source_url,
                )
            )

        for span_match in SJTU_CS_SPAN_PATTERN.finditer(block_html):
            span_html = span_match.group("body")
            if "<a" in span_html.lower():
                continue
            name_text = normalize_text(strip_html_tags(unescape(span_html)))
            name = extract_sjtu_cs_name_candidate(name_text)
            if not name:
                continue

            interests = [institute] if institute else []
            profiles.append(
                TeacherProfile(
                    name=name,
                    profile_url=None,
                    email=None,
                    interests=interests,
                    title=None,
                    source_url=source_url,
                )
            )

    return profiles


def extract_sjtu_cs_main_profiles(_html: str, source_url: str) -> List[TeacherProfile]:
    ajax_content = fetch_sjtu_cs_ajax_content()
    ajax_profiles = extract_sjtu_cs_ajax_profiles(ajax_content, source_url=source_url)
    if ajax_profiles:
        return ajax_profiles

    fallback_html = fetch_html(CSE_FALLBACK_URL)
    return extract_sjtu_cse_people_profiles(fallback_html, source_url=CSE_FALLBACK_URL)


def extract_sjtu_gift_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    for match in GIFT_TEACHER_ANCHOR_PATTERN.finditer(html):
        href = normalize_text(match.group("href"))
        body_html = match.group("body")
        name = normalize_text(strip_html_tags(unescape(body_html))).replace(" ", "")
        if not is_chinese_name(name):
            continue

        context_text = extract_context_text(html, start=match.start(), end=match.end(), window=500)
        emails = EMAIL_PATTERN.findall(context_text)
        email = emails[0].lower() if emails else None
        title = extract_title(context_text)

        interests = []
        interests_match = re.search(
            r"(?:研究方向|研究领域|Research\s*Interests?)\s*[:：]?\s*([^\n\r]{2,160})",
            context_text,
            flags=re.IGNORECASE,
        )
        if interests_match:
            interests = split_interests(interests_match.group(1))

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


def extract_sjtu_gc_profiles(html: str, source_url: str) -> List[TeacherProfile]:
    profiles: List[TeacherProfile] = []

    for match in GC_TEACHER_ANCHOR_PATTERN.finditer(html):
        href = normalize_text(match.group("href"))
        body_html = match.group("body")
        name = normalize_text(strip_html_tags(unescape(body_html)))
        if not ENGLISH_NAME_PATTERN.fullmatch(name):
            continue

        context_text = extract_context_text(html, start=match.start(), end=match.end(), window=500)
        emails = EMAIL_PATTERN.findall(context_text)
        email = emails[0].lower() if emails else None
        title = extract_title(context_text)

        interests = []
        interests_match = re.search(
            r"(?:Research\s*Interests?|研究方向|研究领域)\s*[:：]?\s*([^\n\r]{2,160})",
            context_text,
            flags=re.IGNORECASE,
        )
        if interests_match:
            interests = split_interests(interests_match.group(1))

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


def supports_sjtu_soai_zzjs(url: str) -> bool:
    return url.startswith("https://soai.sjtu.edu.cn/cn/faculty/zzjs")


def supports_sjtu_soai_spkz(url: str) -> bool:
    return url.startswith("https://soai.sjtu.edu.cn/cn/teacher/spkz")


def supports_sjtu_cs_main(url: str) -> bool:
    return url.startswith("https://www.cs.sjtu.edu.cn/jiaoshiml.html")


def supports_sjtu_cse_people(url: str) -> bool:
    return url.startswith("https://cs.sjtu.edu.cn/cse/People.aspx")


def supports_sjtu_gift(url: str) -> bool:
    return url.startswith("https://gift.sjtu.edu.cn/faculty")


def supports_sjtu_gc(url: str) -> bool:
    return url.startswith("https://gc.sjtu.edu.cn/about/faculty-staff/faculty-directory")


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="sjtu_soai_zzjs_card",
            matcher=supports_sjtu_soai_zzjs,
            extractor=lambda _html: [],
            profile_extractor=extract_sjtu_soai_zzjs_profiles,
        ),
        Rule(
            name="sjtu_soai_spkz_card",
            matcher=supports_sjtu_soai_spkz,
            extractor=lambda _html: [],
            profile_extractor=extract_sjtu_soai_spkz_profiles,
        ),
        Rule(
            name="sjtu_cs_main_to_cse_fallback",
            matcher=supports_sjtu_cs_main,
            extractor=lambda _html: [],
            profile_extractor=extract_sjtu_cs_main_profiles,
        ),
        Rule(
            name="sjtu_cse_people_list",
            matcher=supports_sjtu_cse_people,
            extractor=lambda _html: [],
            profile_extractor=extract_sjtu_cse_people_profiles,
        ),
        Rule(
            name="sjtu_gift_faculty_detail",
            matcher=supports_sjtu_gift,
            extractor=lambda _html: [],
            profile_extractor=extract_sjtu_gift_profiles,
        ),
        Rule(
            name="sjtu_gc_faculty_detail",
            matcher=supports_sjtu_gc,
            extractor=lambda _html: [],
            profile_extractor=extract_sjtu_gc_profiles,
        ),
    ]
