from __future__ import annotations

import re
from html import unescape
from typing import List

from teacher_list_core import Rule


def strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def extract_thu_cs_h2_anchor_names(html: str) -> List[str]:
    pattern = re.compile(r"<h2>\s*<a[^>]*>(.*?)</a>\s*</h2>", re.IGNORECASE | re.DOTALL)
    candidates = pattern.findall(html)
    return [strip_html_tags(unescape(name)) for name in candidates]


def supports_thu_cs(url: str) -> bool:
    return url.startswith("https://www.cs.tsinghua.edu.cn/szzk/jzgml.htm")


def get_rules() -> List[Rule]:
    return [
        Rule(
            name="thu_cs_h2_anchor",
            matcher=supports_thu_cs,
            extractor=extract_thu_cs_h2_anchor_names,
        )
    ]
