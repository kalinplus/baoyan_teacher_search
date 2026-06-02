#!/usr/bin/env python3
"""Minimal Stage-2 pipeline: explicit author_id -> scholar profile -> structured outputs."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from scholar.author_id_resolver import AuthorIdResolver


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
UNIVERSITY_CONFIG_PATH = ROOT_DIR / "config" / "universities.json"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class ScholarAuthorClient:
    """Fetch and normalize author profile data from SerpApi by author_id."""

    def __init__(self, serpapi_key: str, timeout: int = 60, endpoint: str = SERPAPI_ENDPOINT):
        if not serpapi_key:
            raise RuntimeError("Missing environment variable: SERPAPI_KEY")
        self.serpapi_key = serpapi_key
        self.timeout = timeout
        self.endpoint = endpoint
        self.max_attempts = 3
        self.retry_timeout_step = 30

    def _request_with_retry(self, *, author_id: str) -> requests.Response:
        for attempt in range(1, self.max_attempts + 1):
            attempt_timeout = self.timeout + (attempt - 1) * self.retry_timeout_step
            try:
                response = requests.get(
                    self.endpoint,
                    params={
                        "api_key": self.serpapi_key,
                        "engine": "google_scholar_author",
                        "author_id": author_id,
                        "hl": "en",
                        "sort": "pubdate",
                        "num": "100",
                    },
                    timeout=attempt_timeout,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException:
                if attempt >= self.max_attempts:
                    raise

    def query_structured_info(self, author_id: str) -> Dict[str, Any]:
        """Main method: query structured metrics by explicit Google Scholar author_id."""
        response = self._request_with_retry(author_id=author_id)
        payload = response.json()

        if payload.get("error"):
            raise RuntimeError(f"SerpApi error: {payload['error']}")

        author = payload.get("author", {})
        cited_by = payload.get("cited_by", {})
        table = cited_by.get("table", []) or []
        graph = cited_by.get("graph", []) or []
        articles = payload.get("articles", []) or []
        pagination = payload.get("serpapi_pagination", {}) or {}
        publications_truncated = bool(pagination.get("next"))

        interests = []
        for item in author.get("interests", []) or []:
            if isinstance(item, dict) and item.get("title"):
                interests.append(item["title"])

        return {
            "name": author.get("name") or "",
            "affiliations": author.get("affiliations") or "",
            "email": author.get("email") or "",
            "interests": interests,
            "citations_all": self._get_table_metric(table, "citations", "all"),
            "citations_last_1y": self._citations_from_graph(graph, recent_years=1),
            "citations_last_3y": self._citations_from_graph(graph, recent_years=3),
            "citations_last_5y": self._citations_from_graph(graph, recent_years=5),
            "publications_total": self._publication_count(articles),
            "publications_last_1y": self._publication_count(articles, recent_years=1),
            "publications_last_3y": self._publication_count(articles, recent_years=3),
            "publications_last_5y": self._publication_count(articles, recent_years=5),
            "publications_truncated": publications_truncated,
            "h_index_all": self._get_table_metric(table, "h_index", "all"),
            "i10_index_all": self._get_table_metric(table, "i10_index", "all"),
        }

    @staticmethod
    def _parse_int(value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            digits = re.sub(r"[^0-9]", "", value)
            if digits:
                return int(digits)
        return 0

    @classmethod
    def _get_table_metric(cls, table: List[Dict[str, Any]], metric_key: str, period_key: str = "all") -> int:
        for row in table:
            metric_obj = row.get(metric_key)
            if isinstance(metric_obj, dict):
                return cls._parse_int(metric_obj.get(period_key))
        return 0

    @classmethod
    def _citations_from_graph(cls, graph: List[Dict[str, Any]], recent_years: int) -> int:
        now_year = datetime.now().year
        start_year = now_year - (recent_years - 1)
        total = 0
        for item in graph:
            year = cls._parse_int(item.get("year"))
            citations = cls._parse_int(item.get("citations"))
            if year >= start_year:
                total += citations
        return total

    @classmethod
    def _publication_count(cls, articles: List[Dict[str, Any]], recent_years: Optional[int] = None) -> int:
        if recent_years is None:
            return len(articles)

        now_year = datetime.now().year
        start_year = now_year - (recent_years - 1)
        count = 0
        for article in articles:
            year = cls._parse_int(article.get("year"))
            if year >= start_year:
                count += 1
        return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch minimal teacher profile from Google Scholar")
    parser.add_argument("--school", required=True, help="School name or alias")
    parser.add_argument("--teacher", required=True, help="Teacher name")
    parser.add_argument("--author-id", default="", help="Optional explicit Google Scholar author_id")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds (default: 60)",
    )
    return parser.parse_args()


def load_university_mapping(config_path: Path) -> Dict[str, List[str]]:
    if not config_path.exists():
        raise FileNotFoundError(f"University mapping not found: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    return value.strip().casefold()


def normalize_school_name(raw_school: str, mapping: Dict[str, List[str]]) -> str:
    lookup: Dict[str, str] = {}
    for canonical, aliases in mapping.items():
        lookup[normalize_text(canonical)] = canonical
        for alias in aliases:
            lookup[normalize_text(alias)] = canonical

    normalized = lookup.get(normalize_text(raw_school))
    if normalized:
        return normalized

    raise ValueError(f"Unknown school alias: {raw_school}")


def build_summary(result: Dict[str, Any]) -> str:
    lines = [
        "# 保研老师检索摘要",
        "",
        f"- 学校: {result['matched_school']}",
        f"- 老师: {result['matched_teacher']}",
        f"- 匹配作者: {result['name']} ({result['author_id']})",
        f"- 单位: {result['affiliations']}",
        f"- 邮箱: {result['email']}",
        f"- 研究方向: {', '.join(result['interests']) if result['interests'] else 'N/A'}",
        f"- 总引用: {result['citations_all']}",
        f"- 近1年引用: {result['citations_last_1y']}",
        f"- 近3年引用: {result['citations_last_3y']}",
        f"- 近5年引用: {result['citations_last_5y']}",
        f"- 总发文(抓取到): {result['publications_total']}",
        f"- 近1年发文: {result['publications_last_1y']}",
        f"- 近3年发文: {result['publications_last_3y']}",
        f"- 近5年发文: {result['publications_last_5y']}",
        f"- 发文统计是否截断: {'是' if result['publications_truncated'] else '否'}",
        f"- h-index: {result['h_index_all']}",
        f"- i10-index: {result['i10_index_all']}",
        "",
        "## 说明",
        "- 阶段2支持两种模式：显式 author_id 或学校+老师自动发现 author_id。",
        "- 自动发现存在同名误匹配风险，请结合缓存和结果复核。",
    ]
    return "\n".join(lines)


def main() -> int:
    load_dotenv(dotenv_path=ROOT_DIR / ".env")
    args = parse_args()

    serpapi_key = os.getenv("SERPAPI_KEY", "").strip()

    university_mapping = load_university_mapping(UNIVERSITY_CONFIG_PATH)
    canonical_school = normalize_school_name(args.school, university_mapping)

    out_dir = Path(args.out_dir)
    teacher_name = args.teacher.strip()
    author_id = args.author_id.strip()

    if author_id:
        author_id_source = "manual_author_id"
    else:
        scraperapi_key = os.getenv("SCRAPERAPI_KEY", "").strip()
        resolver = AuthorIdResolver(scraperapi_key=scraperapi_key, timeout=args.timeout)
        cache_path = out_dir / ".cache" / "author_id_cache.json"
        resolved = resolver.resolve(
            school=canonical_school,
            teacher=teacher_name,
            cache_path=cache_path,
            school_aliases=university_mapping.get(canonical_school, []),
        )
        author_id = resolved["author_id"]
        author_id_source = resolved["source"]

    scholar_client = ScholarAuthorClient(serpapi_key=serpapi_key, timeout=args.timeout)
    profile = scholar_client.query_structured_info(author_id=author_id)

    result = {
        "author_id": author_id,
        "name": profile["name"],
        "affiliations": profile["affiliations"],
        "email": profile["email"],
        "interests": profile["interests"],
        "citations_all": profile["citations_all"],
        "citations_last_1y": profile["citations_last_1y"],
        "citations_last_3y": profile["citations_last_3y"],
        "citations_last_5y": profile["citations_last_5y"],
        "publications_total": profile["publications_total"],
        "publications_last_1y": profile["publications_last_1y"],
        "publications_last_3y": profile["publications_last_3y"],
        "publications_last_5y": profile["publications_last_5y"],
        "publications_truncated": profile["publications_truncated"],
        "h_index_all": profile["h_index_all"],
        "i10_index_all": profile["i10_index_all"],
        "source": f"{author_id_source},scholar_author",
        "matched_school": canonical_school,
        "matched_teacher": teacher_name,
    }

    target_dir = out_dir / canonical_school / teacher_name
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target_dir / "summary.md").write_text(build_summary(result), encoding="utf-8")

    print(f"Saved result: {target_dir / 'result.json'}")
    print(f"Saved summary: {target_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
