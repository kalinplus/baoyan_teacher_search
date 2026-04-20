#!/usr/bin/env python3
"""Scrape teacher profile pages for richer information: research fields, bio, email, works."""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional

import requests

from utils import configure_logging, get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

NAV_PATTERNS = re.compile(
    r"(?:首页|关于我们|师资(?:队伍|团队)|教研(?:系列|人员)?|科学(?:研究)?"
    r"|人才培养|学生工作|杰出人才|荣誉学衔|教学(?:系列|中心)?"
    r"|研究生|本科生|博士后|教辅行政|光荣退休"
    r"|学科建设|科研进展|学术讲座|科研基地|讲座信息"
    r"|国际化|招贤纳士|教工之家"
    r"|新闻|通知|公告|招生|下载|资源|留言|联系我们|联系方式|返回"
    r"|版权|地址|邮编|浏览|推荐|抱歉|响应式|会议室预定|下一页"
    r"|Open\s*Menu|Close\s*Menu|International\s*Student"
    r"|您现在的位置|按名字|院友活动|校友企业|基金捐赠|办公服务)",
    re.IGNORECASE,
)

JS_NAV_PATTERN = re.compile(
    r"(?:_jsq_|appElement|document\.|window\.|querySelector|getElementById"
    r"|innerHTML|\.jsp|\.css|\.js\?|addEventListener|onclick"
    r"|function\s*\(|new\s+RegExp|\.exec\(|\.match\(|\.replace\("
    r"|console\.|\.write\(|\.writeln\(|\.readyState|\.createElement"
    r"|\.appendChild|var\s+\w+\s*=|let\s+\w+\s*=|const\s+\w+\s*="
    r"|#appu\d|\.qwss|AOS\.init|\.show\(|\.hide\(|\.html\(\)"
    r"|响应式|浏览器|谷歌|火狐)",
    re.IGNORECASE,
)

# Order matters: longer/more-specific patterns first so they score higher
RESEARCH_KEYWORDS = re.compile(
    r"(?:主要研究方向|Research\s*Interests?|研究方向|研究领域|研究兴趣)",
    re.IGNORECASE,
)

BIO_KEYWORDS = re.compile(
    r"(?:个人简介|简介|个人概况|Introduction|Biography|个人介绍)",
    re.IGNORECASE,
)

WORKS_KEYWORDS = re.compile(
    r"(?:代表性工作|代表论文|代表性学术论著|代表性论著|Representative\s*Works?|代表学术论著)",
    re.IGNORECASE,
)

RECRUITING_KEYWORDS = re.compile(
    r"(?:招收|招生|recruiting|accepting)",
    re.IGNORECASE,
)

RECRUITING_NEGATIVE = re.compile(
    r"(?:暂停|暂不|停止|不再|not\s*recruiting|not\s*accepting)",
    re.IGNORECASE,
)

HOMEPAGE_PATTERN = re.compile(
    r"(?:个人主页|Homepage|Personal\s*Page)\s*[：:]\s*\n?\s*(https?://[^\s<\"]+)",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(
    r"([\w.+-]+)\s*(?:at|@)\s*([\w.-]+\.\w+)",
    re.IGNORECASE,
)

EMAIL_STANDARD = re.compile(
    r"([\w.+-]+)@([\w.-]+\.\w+)",
    re.IGNORECASE,
)

TITLE_PATTERN = re.compile(
    r"(?:讲席教授|长聘教授|教授|长聘副教授|副教授|助理教授|研究员|副研究员|助理研究员|高级工程师|讲师)",
)

CONFERENCE_PATTERN = re.compile(
    r"\b(CVPR|ICCV|ECCV|ACL|EMNLP|NAACL|NeurIPS|ICML|ICLR|AAAI|IJCAI"
    r"|KDD|SIGIR|WWW|SIGMOD|VLDB|ICDE|SOSP|OSDI|NSDI|EuroSys|ASPLOS"
    r"|ISCA|MICRO|HPCA|DAC|ICCAD|CCS|USENIX\s*Security|IEEE\s*S&P"
    r"|NDSS|INFOCOM|SIGCOMM|MobiCom|MobiSys|SenSys|CoNEXT"
    r"|IEEE\s*Trans\.\s*\w+|ACM\s*Trans\.\s*\w+"
    r"|TIP|TPAMI|TKDE|TOS|TON|JSAC|TMC|TOC|TCAD)\b",
)

CHINESE_NAME_PATTERN = re.compile(r"^[\u4e00-\u9fff]{2,4}$")


# ---------------------------------------------------------------------------
# HTML → text
# ---------------------------------------------------------------------------

def fetch_html(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    return resp.text


def html_to_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = unescape(text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def is_nav_line(line: str) -> bool:
    if len(line) < 3:
        return True
    if len(line) <= 16 and NAV_PATTERNS.search(line):
        return True
    if JS_NAV_PATTERN.search(line):
        return True
    if CHINESE_NAME_PATTERN.fullmatch(line):
        return False
    if re.match(r"^[\d（()）\-、，。；：,.;:\s]+$", line):
        return True
    return False


JS_LINE_PATTERN = re.compile(
    r"^\s*(?:var |let |const |function |document\.|window\.|\$\(|if\s*\(|for\s*\(|"
    r"while\s*\(|else\s*\{|}\s*$|\{|\}|/\*|\*/|<!--|-->|"
    r"\}\s*$|^\+\s*[\"']|\+\s*str|\+\s*\n)",
)


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.split("\n") if line.strip() and not is_nav_line(line)]
    lines = [l for l in lines if not JS_LINE_PATTERN.match(l)]
    # deduplicate: lines appearing 2+ times are likely nav (menus repeat for mobile/desktop)
    from collections import Counter
    line_counts = Counter(lines)
    lines = [l for l in lines if line_counts[l] < 2]
    # remove blocks of 3+ consecutive short lines that all match nav keywords
    cleaned: list[str] = []
    nav_run: list[str] = []
    SHORT_LINE_MAX = 18
    NAV_RUN_THRESHOLD = 3
    for line in lines:
        is_short_nav = len(line) <= SHORT_LINE_MAX and NAV_PATTERNS.search(line)
        if is_short_nav:
            nav_run.append(line)
        else:
            if len(nav_run) >= NAV_RUN_THRESHOLD:
                nav_run.clear()
            else:
                cleaned.extend(nav_run)
                nav_run.clear()
            cleaned.append(line)
    if len(nav_run) < NAV_RUN_THRESHOLD:
        cleaned.extend(nav_run)
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def _extract_section(text: str, keyword_pattern: re.Pattern, max_chars: int = 2000) -> str:
    """Find a heading-like match of keyword_pattern with substantive content after it."""
    matches = list(keyword_pattern.finditer(text))
    if not matches:
        return ""

    EMBEDDED_TEXT_CHARS = set("为的与和是了过等在以其中")

    for match in matches:
        start = match.end()
        # Skip if keyword is embedded in running text (e.g. "研究领域为")
        next_char = text[start:start + 1]
        if next_char and next_char in EMBEDDED_TEXT_CHARS:
            continue

        section = text[start:start + max_chars]
        content_lines = [l for l in section.split("\n") if l.strip() and not is_nav_line(l)]
        if not content_lines:
            continue
        # First content line must be substantive (> 8 chars) to distinguish from nav
        if len(content_lines[0]) < 8:
            continue

        # cut at next major heading-like keyword if present
        cut_patterns = [
            RESEARCH_KEYWORDS, BIO_KEYWORDS, WORKS_KEYWORDS,
            re.compile(r"(?:教育背景|工作经历|论文发表|代表性|主要荣誉|科研项目|社会兼职|获奖|课程|教学|办公电话|电子邮件|办公地址)", re.I),
        ]
        earliest = len(section)
        for pat in cut_patterns:
            m = pat.search(section)
            if m and m.start() < earliest:
                earliest = m.start()
        if earliest < len(section):
            section = section[:earliest]

        result_lines = [l.strip() for l in section.split("\n") if l.strip() and not is_nav_line(l)]
        return "\n".join(result_lines).strip()

    return ""


def extract_research_fields(text: str) -> List[str]:
    section = _extract_section(text, RESEARCH_KEYWORDS, max_chars=500)
    if not section:
        return []
    # take first 1-2 sentences
    sentences = re.split(r"[。\n]", section)
    raw = sentences[0] if sentences else section
    # remove leading colon/bracket
    raw = re.sub(r"^[：:：\s]+", "", raw).strip()
    if not raw:
        return []
    parts = re.split(r"[、,，;；/|]+", raw)
    fields = []
    for part in parts:
        part = part.strip()
        if 2 <= len(part) <= 40 and not is_nav_line(part):
            fields.append(part)
    return fields[:10]


def extract_bio(text: str, research_fields: List[str], representative_works: Optional[str]) -> str:
    section = _extract_section(text, BIO_KEYWORDS, max_chars=1000)
    if section and len(section) > 30:
        return section[:500].strip()
    # fallback: concatenate research_fields + representative_works
    parts = []
    if research_fields:
        parts.append("、".join(research_fields))
    if representative_works:
        parts.append(representative_works)
    return " ".join(parts)[:500].strip()


def extract_email(text: str) -> Optional[str]:
    # "xxx at xxx.edu.cn" pattern (北大 AI style)
    m = EMAIL_PATTERN.search(text)
    if m:
        return f"{m.group(1).lower()}@{m.group(2).lower()}"
    # standard "xxx@xxx.edu.cn"
    m = EMAIL_STANDARD.search(text)
    if m:
        return f"{m.group(1).lower()}@{m.group(2).lower()}"
    return None


def extract_representative_works(text: str) -> str:
    section = _extract_section(text, WORKS_KEYWORDS, max_chars=2000)
    if not section:
        return ""
    return section.strip()


def extract_personal_homepage(text: str) -> Optional[str]:
    m = HOMEPAGE_PATTERN.search(text)
    if m:
        url = m.group(1).strip().rstrip("/")
        return url
    return None


def extract_recruiting_status(text: str) -> str:
    pos_matches = list(RECRUITING_KEYWORDS.finditer(text))
    if not pos_matches:
        return "unknown"
    for m in pos_matches:
        context_start = max(0, m.start() - 30)
        context_end = min(len(text), m.end() + 80)
        context = text[context_start:context_end]
        if RECRUITING_NEGATIVE.search(context):
            return "not_recruiting"
    return "recruiting"


def extract_conferences(text: str) -> List[str]:
    matches = CONFERENCE_PATTERN.findall(text)
    return list(dict.fromkeys(matches))


def extract_title(text: str) -> Optional[str]:
    matches = TITLE_PATTERN.findall(text)
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Single profile scrape
# ---------------------------------------------------------------------------

def scrape_profile(url: str, timeout: int = 30) -> Dict[str, object]:
    html = fetch_html(url, timeout=timeout)
    text = clean_text(html_to_text(html))

    research_fields = extract_research_fields(text)
    works = extract_representative_works(text)
    bio = extract_bio(text, research_fields, works)
    email = extract_email(text)
    homepage = extract_personal_homepage(text)
    recruiting = extract_recruiting_status(text)
    conferences = extract_conferences(text)
    title = extract_title(text)

    return {
        "full_text": text,
        "research_fields": research_fields,
        "bio": bio,
        "email": email,
        "title": title,
        "representative_works": works if works else None,
        "personal_homepage": homepage,
        "recruiting_status": recruiting,
        "conferences": conferences if conferences else None,
    }


# ---------------------------------------------------------------------------
# Batch scrape with concurrency control
# ---------------------------------------------------------------------------

def _scrape_one(
    teacher: Dict[str, object],
    timeout: int,
    existing_homepages: set,
) -> tuple:
    name = teacher["name"]
    profile_url = teacher.get("profile_url")
    if not profile_url or profile_url in existing_homepages:
        return name, None, "skipped"

    try:
        result = scrape_profile(str(profile_url), timeout=timeout)
        return name, result, None
    except Exception as exc:
        logger.warning("Failed to scrape profile for %s (%s): %s", name, profile_url, exc)
        return name, None, str(exc)


def scrape_profiles(
    input_path: str,
    output_path: str,
    timeout: int = 30,
    concurrency: int = 3,
    delay: float = 0.5,
) -> Dict[str, int]:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    profiles: List[Dict[str, object]] = data.get("teacher_profiles", [])

    # collect already-scraped URLs
    existing_homepages: set = set()
    for p in profiles:
        if p.get("homepage"):
            existing_homepages.add(p.get("profile_url"))

    stats = {"total": len(profiles), "scraped": 0, "skipped": 0, "failed": 0}

    targets = [(i, p) for i, p in enumerate(profiles) if p.get("profile_url") and p["profile_url"] not in existing_homepages]
    logger.info("Scraping profiles: %d targets, %d already cached", len(targets), stats["total"] - len(targets))

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {}
        for i, teacher in targets:
            future = pool.submit(_scrape_one, teacher, timeout, existing_homepages)
            futures[future] = (i, teacher["name"])
            time.sleep(delay)

        for future in as_completed(futures):
            idx, name = futures[future]
            teacher_name, result, error = future.result()

            if error and error == "skipped":
                stats["skipped"] += 1
                continue
            if error:
                stats["failed"] += 1
                profiles[idx]["homepage"] = None
                continue

            profiles[idx]["homepage"] = result
            # backfill email and title if missing
            if not profiles[idx].get("email") and result.get("email"):
                profiles[idx]["email"] = result["email"]
            if not profiles[idx].get("title") and result.get("title"):
                profiles[idx]["title"] = result["title"]
            stats["scraped"] += 1
            logger.info("Scraped %s: research=%s, email=%s", name, result.get("research_fields"), result.get("email"))

    data["teacher_profiles"] = profiles
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %s: scraped=%d, skipped=%d, failed=%d", output_path, stats["scraped"], stats["skipped"], stats["failed"])
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape teacher profile pages")
    parser.add_argument("--input", required=True, help="Input teachers.json path")
    parser.add_argument("--output", required=True, help="Output teachers.json path")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout")
    parser.add_argument("--concurrency", type=int, default=3, help="Max concurrent requests")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests in seconds")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)
    stats = scrape_profiles(args.input, args.output, timeout=args.timeout, concurrency=args.concurrency, delay=args.delay)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
