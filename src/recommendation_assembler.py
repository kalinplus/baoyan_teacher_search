from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def _build_recommendation_reason(candidate: Dict[str, Any], scholar_metrics: Dict[str, Any]) -> str:
    tier = str(candidate.get("tier", ""))
    score = int(candidate.get("score", 0))
    citations_all = int(scholar_metrics.get("citations_all", 0))
    publications_last_3y = int(scholar_metrics.get("publications_last_3y", 0))
    return (
        f"prescreen_tier={tier}; prescreen_score={score}; "
        f"citations_all={citations_all}; publications_last_3y={publications_last_3y}"
    )


def _build_risk_flags(candidate: Dict[str, Any], scholar_metrics: Dict[str, Any]) -> List[str]:
    flags: List[str] = []

    tier = str(candidate.get("tier", ""))
    if tier == "C":
        flags.append("low_prescreen_tier")

    if bool(scholar_metrics.get("publications_truncated")):
        flags.append("publications_truncated")

    if int(scholar_metrics.get("publications_last_3y", 0)) == 0:
        flags.append("low_recent_publications")

    if not scholar_metrics.get("email"):
        flags.append("missing_scholar_email")

    return flags


def assemble_final_recommendations(
    *,
    school: str,
    college: str,
    top_candidates: List[Dict[str, Any]],
    resolved_candidates: List[Dict[str, Any]],
    scholar_results: List[Dict[str, Any]],
    failed_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    candidate_by_teacher = {str(item["name"]): item for item in top_candidates}
    resolved_by_teacher = {str(item["teacher"]): item for item in resolved_candidates}

    recommendations: List[Dict[str, Any]] = []
    for scholar_item in scholar_results:
        teacher = str(scholar_item["teacher"])
        candidate = candidate_by_teacher[teacher]
        resolved = resolved_by_teacher[teacher]
        scholar_metrics = dict(scholar_item["scholar_metrics"])

        recommendations.append(
            {
                "teacher": teacher,
                "prescreen_score": int(candidate.get("score", 0)),
                "prescreen_tier": candidate.get("tier"),
                "prescreen_reasons": list(candidate.get("reasons", [])),
                "author_id": resolved["author_id"],
                "author_id_source": resolved["author_id_source"],
                "scholar_metrics": scholar_metrics,
                "recommendation_reason": _build_recommendation_reason(candidate, scholar_metrics),
                "risk_flags": _build_risk_flags(candidate, scholar_metrics),
            }
        )

    return {
        "school": school,
        "college": college,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_candidates": len(top_candidates),
        "resolved_candidates": len(recommendations),
        "failed_candidates": len(failed_candidates),
        "failed_candidate_details": failed_candidates,
        "recommendations": recommendations,
    }
