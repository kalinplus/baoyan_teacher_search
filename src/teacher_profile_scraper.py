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

def _fetch_html_with_weak_ssl(url: str, timeout: int = 30) -> str:
    import ssl

    import urllib3

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("ALL:@SECLEVEL=0")
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    http = urllib3.PoolManager(ssl_context=ctx)
    resp = http.request("GET", url, timeout=timeout)
    return resp.data.decode("utf-8", errors="replace")


def fetch_html(url: str, timeout: int = 30) -> str:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.SSLError:
        return _fetch_html_with_weak_ssl(url, timeout=timeout)

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
# SJTU CS structured profile scrape
# ---------------------------------------------------------------------------

SJTU_CS_PROFILE_URL_PATTERN = re.compile(r"https?://www\.cs\.sjtu\.edu\.cn/jiaoshiml/[^/]+\.html")


def _extract_sjtu_cs_js_info(html: str) -> Dict[str, Optional[str]]:
    """Extract structured fields from the .js-info section."""
    result: Dict[str, Optional[str]] = {
        "name": None,
        "title": None,
        "email": None,
        "phone": None,
        "address": None,
        "institute": None,
        "personal_homepage": None,
    }
    start = html.find('<div class="js-info"')
    if start == -1:
        return result
    # Find the matching closing </div> by tracking nesting depth
    tag_start = html.find(">", start)
    if tag_start == -1:
        return result
    tag_start += 1
    depth = 1
    pos = tag_start
    while pos < len(html) and depth > 0:
        next_open = html.find("<div", pos)
        next_close = html.find("</div>", pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6
    info_html = html[start:pos]

    m = re.search(r'<div class="name">(.*?)</div>', info_html)
    if m:
        result["name"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    m = re.search(r'<div class="zw">(.*?)</div>', info_html)
    if m:
        result["title"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    dt_start = info_html.find('<div class="dt">')
    if dt_start != -1:
        dt_html = info_html[dt_start:]
        for p_match in re.finditer(r"<p>(.*?)</p>", dt_html):
            p_clean = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
            if p_clean.startswith("邮箱："):
                result["email"] = p_clean.replace("邮箱：", "").strip()
            elif p_clean.startswith("电话："):
                result["phone"] = p_clean.replace("电话：", "").strip()
            elif p_clean.startswith("地址："):
                result["address"] = p_clean.replace("地址：", "").strip()
            elif p_clean.startswith("所在研究所："):
                result["institute"] = p_clean.replace("所在研究所：", "").strip()
            elif p_clean.startswith("个人主页："):
                href_match = re.search(r'href=["\']([^"\']+)["\']', p_match.group(1))
                if href_match:
                    result["personal_homepage"] = href_match.group(1).strip()

    return result


def _extract_sjtu_cs_bio(html: str) -> str:
    """Extract full bio text from the '个人简介' section inside .js-dt."""
    start = html.find('<div class="js-dt">')
    if start == -1:
        return ""
    end = html.find('<div class="footer">', start)
    if end == -1:
        end = html.find('<div class="clear">', start)
    if end == -1:
        end = start + 20000
    dt_html = html[start:end]

    item_pattern = re.compile(
        r'<div class="item item2">\s*<div class="name"><p>(.*?)</p></div>\s*<div class="txt">(.*?)</div>\s*</div>',
        re.DOTALL,
    )
    for title_match, content_match in item_pattern.findall(dt_html):
        title = re.sub(r"<[^>]+>", "", title_match).strip()
        if title == "个人简介":
            bio = re.sub(r"<[^>]+>", " ", content_match)
            bio = re.sub(r"\s+", " ", bio).strip()
            return bio
    return ""


def _scrape_sjtu_cs_profile(html: str, url: str) -> Dict[str, object]:
    """Structured scrape for SJTU CS faculty profile pages.

    Produces a clean, structured full_text for LLM consumption.
    """
    info = _extract_sjtu_cs_js_info(html)
    bio = _extract_sjtu_cs_bio(html)

    lines: list[str] = []
    if info.get("name"):
        lines.append(f"姓名：{info['name']}")
    if info.get("title"):
        lines.append(f"职称：{info['title']}")
    if info.get("email"):
        lines.append(f"邮箱：{info['email']}")
    if info.get("phone"):
        lines.append(f"电话：{info['phone']}")
    if info.get("address"):
        lines.append(f"地址：{info['address']}")
    if info.get("institute"):
        lines.append(f"所在研究所：{info['institute']}")
    if info.get("personal_homepage"):
        lines.append(f"个人主页：{info['personal_homepage']}")

    if bio:
        lines.append("")
        lines.append("个人简介：")
        lines.append(bio)

    full_text = "\n".join(lines)

    # Derive research_fields from bio text (SJTU pages don't have a dedicated section)
    research_fields: list[str] = []
    if bio:
        patterns = [
            re.compile(r"主要研究方向为\s*[:：]?\s*([^。\n]+)"),
            re.compile(r"研究方向为\s*[:：]?\s*([^。\n]+)"),
            re.compile(r"研究方向\s*[:：]\s*([^。\n]+)"),
            re.compile(r"研究兴趣主要集中在\s*([^。\n]+)"),
            re.compile(r"主要研究领域为\s*[:：]?\s*([^。\n]+)"),
        ]
        # Boundary words that indicate the description has moved past research fields
        boundary_words = ("研究成果", "曾获", "目前担任", "曾任", "在", "发表", "获得",
                          "荣誉", "论文", "项目", "基金", "主持", "参与", "合作")
        for pat in patterns:
            m = pat.search(bio)
            if m:
                raw = m.group(1).strip()
                # Cut entire raw at first boundary word before splitting
                for bw in boundary_words:
                    idx = raw.find(bw)
                    if idx != -1:
                        raw = raw[:idx].strip().rstrip("，,、")
                        break
                parts = re.split(r"[、,，;；/|]+", raw)
                for part in parts:
                    part = part.strip()
                    # Skip descriptive fragments
                    if part.startswith("涵盖了") or part.startswith("尤其是") or part.endswith("等方面"):
                        continue
                    if 2 <= len(part) <= 40:
                        research_fields.append(part)
                if research_fields:
                    break

    # Keep conference extraction running on the full_text
    conferences = list(dict.fromkeys(CONFERENCE_PATTERN.findall(full_text)))

    return {
        "full_text": full_text,
        "research_fields": research_fields if research_fields else None,
        "bio": bio if bio else None,
        "email": info.get("email"),
        "title": info.get("title"),
        "representative_works": None,
        "personal_homepage": info.get("personal_homepage"),
        "recruiting_status": extract_recruiting_status(full_text),
        "conferences": conferences if conferences else None,
    }


# ---------------------------------------------------------------------------
# THU CS structured profile scrape
# ---------------------------------------------------------------------------

THU_CS_PROFILE_URL_PATTERN = re.compile(r"https?://www\.cs\.tsinghua\.edu\.cn/info/\d+/\d+\.htm")


def _extract_thu_cs_vnews(html: str) -> str:
    start = html.find('<div class="v_news_content">')
    if start == -1:
        m = re.search(r'<div\b[^>]*class=["\'][^"\']*v_news_content[^"\']*["\'][^>]*>', html)
        if not m:
            return ""
        start = m.start()
    tag_start = html.find(">", start)
    if tag_start == -1:
        return ""
    tag_start += 1
    depth = 1
    pos = tag_start
    while pos < len(html) and depth > 0:
        next_open = html.find("<div", pos)
        next_close = html.find("</div>", pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6
    return html[start:pos]


def _scrape_thu_cs_profile(html: str, url: str) -> Dict[str, object]:
    vnews_html = _extract_thu_cs_vnews(html)
    if not vnews_html:
        text = clean_text(html_to_text(html))
        return _scrape_generic_profile(text)

    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    personal_homepage: Optional[str] = None

    p_tags = re.findall(r'<p[^>]*>(.*?)</p>', vnews_html, re.IGNORECASE | re.DOTALL)
    for p_html in p_tags:
        p_text = re.sub(r'<[^>]+>', '', p_html).strip()
        if p_text.startswith('姓名：'):
            name = p_text.replace('姓名：', '').strip()
        elif p_text.startswith('职称：'):
            title = p_text.replace('职称：', '').strip()
        elif p_text.startswith('支撑：'):
            title = p_text.replace('支撑：', '').strip()
        elif p_text.startswith('电话：'):
            phone = p_text.replace('电话：', '').strip()
        elif p_text.startswith('邮箱：'):
            email = p_text.replace('邮箱：', '').strip()
        elif p_text.startswith('主页：'):
            href_match = re.search(r'href=["\']([^"\']+)["\']', p_html)
            personal_homepage = href_match.group(1).strip() if href_match else p_text.replace('主页：', '').strip()
        elif p_text.startswith('个人主页：'):
            href_match = re.search(r'href=["\']([^"\']+)["\']', p_html)
            personal_homepage = href_match.group(1).strip() if href_match else p_text.replace('个人主页：', '').strip()

    # Fallback for alternate template (no 姓名：/职称： prefixes)
    if not name:
        for p_html in p_tags:
            p_text = re.sub(r'<[^>]+>', '', p_html).strip()
            if CHINESE_NAME_PATTERN.fullmatch(p_text):
                name = p_text
                break
    if not title:
        for p_html in p_tags:
            p_text = re.sub(r'<[^>]+>', '', p_html).strip()
            if TITLE_PATTERN.fullmatch(p_text):
                title = p_text
                break
    if not email:
        for p_html in p_tags:
            p_text = re.sub(r'<[^>]+>', '', p_html).strip()
            email_match = EMAIL_STANDARD.search(p_text)
            if email_match:
                email = email_match.group(0).lower()
                break

    sections: Dict[str, str] = {}
    # Primary: <h4><p>Title</p></h4>
    section_pattern = re.compile(
        r'<h4[^>]*>\s*<p[^>]*>(.*?)</p>\s*</h4>\s*(.*?)(?=<h4[^>]*>|$)',
        re.IGNORECASE | re.DOTALL,
    )
    for heading_html, content_html in section_pattern.findall(vnews_html):
        heading = re.sub(r'<[^>]+>', '', heading_html).strip()
        if heading == '研究领域':
            first_p = re.search(r'<p[^>]*>(.*?)</p>', content_html, re.IGNORECASE | re.DOTALL)
            content = re.sub(r'<[^>]+>', ' ', first_p.group(1)).strip() if first_p else ''
        else:
            content = re.sub(r'<[^>]+>', ' ', content_html).strip()
        content = re.sub(r'\s+', ' ', content).strip()
        sections[heading] = content

    # Alternate: <p><strong>Title</strong></p> or <p><b>Title</b></p>
    alt_section_pattern = re.compile(
        r'<p[^>]*>\s*(?:<strong>|<b>)(.*?)(?:</strong>|</b>)\s*</p>\s*(.*?)(?=<p[^>]*>\s*(?:<strong>|<b>)|$)',
        re.IGNORECASE | re.DOTALL,
    )
    for heading_html, content_html in alt_section_pattern.findall(vnews_html):
        heading = re.sub(r'<[^>]+>', '', heading_html).strip()
        if heading in sections:
            continue
        if heading == '研究领域':
            first_p = re.search(r'<p[^>]*>(.*?)</p>', content_html, re.IGNORECASE | re.DOTALL)
            content = re.sub(r'<[^>]+>', ' ', first_p.group(1)).strip() if first_p else ''
        else:
            content = re.sub(r'<[^>]+>', ' ', content_html).strip()
        content = re.sub(r'\s+', ' ', content).strip()
        sections[heading] = content

    research_fields: list[str] = []
    if '研究领域' in sections:
        raw = sections['研究领域']
        parts = re.split(r'[、,，;；/|]+', raw)
        for part in parts:
            part = part.strip()
            if 2 <= len(part) <= 40:
                research_fields.append(part)

    bio = sections.get('研究概况') or sections.get('教育背景') or ""

    lines: list[str] = []
    if name:
        lines.append(f"姓名：{name}")
    if title:
        lines.append(f"职称：{title}")
    if phone:
        lines.append(f"电话：{phone}")
    if email:
        lines.append(f"邮箱：{email}")
    if personal_homepage:
        lines.append(f"个人主页：{personal_homepage}")
    if research_fields:
        lines.append("")
        lines.append(f"研究领域：{'、'.join(research_fields)}")
    if bio:
        lines.append("")
        lines.append("研究概况：")
        lines.append(bio)
    for heading in ['教育背景', '社会兼职', '奖励与荣誉', '学术成果', '工作经历']:
        if heading in sections and sections[heading]:
            lines.append("")
            lines.append(f"{heading}：")
            lines.append(sections[heading])

    full_text = "\n".join(lines)
    conferences = list(dict.fromkeys(CONFERENCE_PATTERN.findall(full_text)))

    return {
        "full_text": full_text,
        "research_fields": research_fields if research_fields else None,
        "bio": bio if bio else None,
        "email": email,
        "title": title,
        "representative_works": sections.get('学术成果') or None,
        "personal_homepage": personal_homepage,
        "recruiting_status": extract_recruiting_status(full_text),
        "conferences": conferences if conferences else None,
    }


def _scrape_generic_profile(text: str) -> Dict[str, object]:
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
# NJU IS structured profile scrape
# ---------------------------------------------------------------------------

NJU_PROFILE_URL_PATTERN = re.compile(r"https?://is\.nju\.edu\.cn/\w+/main\.htm")


def _extract_nju_personinfo(html: str) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {"name": None, "email": None, "office": None}
    start = html.find('<div class="personinfo')
    if start == -1:
        return result
    # Find the matching closing tag by depth tracking
    tag_start = html.find(">", start)
    if tag_start == -1:
        return result
    tag_start += 1
    depth = 1
    pos = tag_start
    while pos < len(html) and depth > 0:
        next_open = html.find('<div', pos)
        next_close = html.find('</div>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6
    info_html = html[start:pos]

    m = re.search(r'<div class="name">(.*?)</div>', info_html)
    if m:
        result["name"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    for zd_match in re.finditer(r'<div class="zd">(.*?)</div>', info_html):
        zd_text = re.sub(r"<[^>]+>", "", zd_match.group(1)).strip()
        if "邮件" in zd_text or "E-mail" in zd_text or "Email" in zd_text:
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", zd_text)
            if email_match:
                result["email"] = email_match.group(0).lower()
        elif "办公" in zd_text or "Office" in zd_text:
            result["office"] = zd_text.split("：", 1)[-1].strip() if "：" in zd_text else ""

    return result


def _extract_nju_cn_con(html: str) -> str:
    """Extract Chinese bio content from the .con section inside .wrapper.cn."""
    cn_start = html.find('<div class="wrapper cn"')
    if cn_start == -1:
        cn_start = 0
    cn_html = html[cn_start:]

    # Find 个人简历 heading then the .con block that follows
    heading_match = re.search(
        r'<div class="name">\s*个人简历\s*</div>\s*<div class="con">',
        cn_html,
        re.IGNORECASE,
    )
    if not heading_match:
        return ""

    start = heading_match.end()
    depth = 1
    pos = start
    while pos < len(cn_html) and depth > 0:
        next_open = cn_html.find('<div', pos)
        next_close = cn_html.find('</div>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6

    con_html = cn_html[start : pos - 6]
    text = re.sub(r"<[^>]+>", "\n", con_html)
    text = unescape(text)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def _scrape_nju_profile(html: str, url: str) -> Dict[str, object]:
    info = _extract_nju_personinfo(html)
    con_text = _extract_nju_cn_con(html)

    lines: list[str] = []
    if info.get("name"):
        lines.append(f"姓名：{info['name']}")
    if info.get("email"):
        lines.append(f"邮箱：{info['email']}")
    if info.get("office"):
        lines.append(f"办公地点：{info['office']}")

    if con_text:
        lines.append("")
        lines.append("个人简历：")
        lines.append(con_text)

    full_text = "\n".join(lines)

    # Extract research fields from bio
    research_fields: list[str] = []
    patterns = [
        re.compile(r"主要从事\s*([^。\n]+)"),
        re.compile(r"研究方向为\s*([^。\n]+)"),
        re.compile(r"研究方向\s*[：:]\s*([^。\n]+)"),
        re.compile(r"研究领域为\s*([^。\n]+)"),
        re.compile(r"研究领域\s*[：:]\s*([^。\n]+)"),
    ]
    for pat in patterns:
        m = pat.search(con_text)
        if m:
            raw = m.group(1).strip()
            parts = re.split(r"[、,，;；/|]+", raw)
            for part in parts:
                part = part.strip()
                if 2 <= len(part) <= 40:
                    research_fields.append(part)
            if research_fields:
                break

    conferences = list(dict.fromkeys(CONFERENCE_PATTERN.findall(full_text)))

    return {
        "full_text": full_text,
        "research_fields": research_fields if research_fields else None,
        "bio": con_text[:800] if con_text else None,
        "email": info.get("email"),
        "title": None,
        "representative_works": None,
        "personal_homepage": None,
        "recruiting_status": extract_recruiting_status(full_text),
        "conferences": conferences if conferences else None,
    }


# ---------------------------------------------------------------------------
# Single profile scrape
# ---------------------------------------------------------------------------

def scrape_profile(url: str, timeout: int = 30) -> Dict[str, object]:
    html = fetch_html(url, timeout=timeout)

    if SJTU_CS_PROFILE_URL_PATTERN.match(url):
        return _scrape_sjtu_cs_profile(html, url)

    if THU_CS_PROFILE_URL_PATTERN.match(url):
        return _scrape_thu_cs_profile(html, url)

    if NJU_PROFILE_URL_PATTERN.match(url):
        return _scrape_nju_profile(html, url)

    text = clean_text(html_to_text(html))
    return _scrape_generic_profile(text)


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
