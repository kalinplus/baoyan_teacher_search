from __future__ import annotations

import os
from typing import Any, Dict, List

from scholar_client import ScholarAuthorClient


def run_scholar_batch(*, resolved_candidates: List[Dict[str, Any]], timeout: int) -> List[Dict[str, Any]]:
    serpapi_key = os.getenv("SERPAPI_KEY", "").strip()
    client = ScholarAuthorClient(serpapi_key=serpapi_key, timeout=timeout)

    results: List[Dict[str, Any]] = []
    for item in resolved_candidates:
        author_id = str(item["author_id"])
        teacher = str(item["teacher"])
        profile = client.query_structured_info(author_id=author_id)
        results.append(
            {
                "teacher": teacher,
                "author_id": author_id,
                "author_id_source": item["author_id_source"],
                "status": "success",
                "error": None,
                "scholar_metrics": profile,
            }
        )

    return results
