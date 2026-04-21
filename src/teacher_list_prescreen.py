from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from teacher_list_helpers import CHINESE_NAME_PATTERN, looks_like_profile_url, normalize_spaces, normalize_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRESCREEN_SCORING_CONFIG_PATH = PROJECT_ROOT / "config" / "prescreen_scoring.json"


def _require_string_list(payload: Dict[str, Any], key: str) -> List[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Prescreen scoring config field '{key}' must be a string array")
    return [normalize_text(item) for item in value if normalize_text(item)]


def _require_non_negative_int(payload: Dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"Prescreen scoring config field '{key}' must be a non-negative integer")
    return value


def load_prescreen_scoring_config(path: Path = DEFAULT_PRESCREEN_SCORING_CONFIG_PATH) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Prescreen scoring config not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Prescreen scoring config must be a JSON object")

    negative_signal_keywords = _require_string_list(payload, "negative_signal_keywords")
    negative_interest_keywords = _require_string_list(payload, "negative_interest_keywords")
    evidence_fields = _require_string_list(payload, "evidence_fields")

    title_keywords_payload = payload.get("title_keywords")
    if not isinstance(title_keywords_payload, dict):
        raise ValueError("Prescreen scoring config field 'title_keywords' must be an object")
    senior_title_keywords = _require_string_list(title_keywords_payload, "senior")
    mid_title_keywords = _require_string_list(title_keywords_payload, "mid")

    weights_payload = payload.get("weights")
    if not isinstance(weights_payload, dict):
        raise ValueError("Prescreen scoring config field 'weights' must be an object")
    weights = {
        "profile_url_bonus": _require_non_negative_int(weights_payload, "profile_url_bonus"),
        "profile_url_person_like_bonus": _require_non_negative_int(weights_payload, "profile_url_person_like_bonus"),
        "missing_profile_url_penalty": _require_non_negative_int(weights_payload, "missing_profile_url_penalty"),
        "has_email_bonus": _require_non_negative_int(weights_payload, "has_email_bonus"),
        "missing_email_penalty": _require_non_negative_int(weights_payload, "missing_email_penalty"),
        "senior_title_bonus": _require_non_negative_int(weights_payload, "senior_title_bonus"),
        "mid_title_bonus": _require_non_negative_int(weights_payload, "mid_title_bonus"),
        "other_title_bonus": _require_non_negative_int(weights_payload, "other_title_bonus"),
        "has_interests_bonus": _require_non_negative_int(weights_payload, "has_interests_bonus"),
        "missing_interests_penalty": _require_non_negative_int(weights_payload, "missing_interests_penalty"),
        "keyword_match_per_hit_bonus": _require_non_negative_int(weights_payload, "keyword_match_per_hit_bonus"),
        "keyword_match_bonus_cap": _require_non_negative_int(weights_payload, "keyword_match_bonus_cap"),
        "negative_keyword_match_per_hit_penalty": _require_non_negative_int(weights_payload, "negative_keyword_match_per_hit_penalty"),
        "negative_keyword_match_penalty_cap": _require_non_negative_int(weights_payload, "negative_keyword_match_penalty_cap"),
        "neutral_penalty": _require_non_negative_int(weights_payload, "neutral_penalty"),
    }

    thresholds_payload = payload.get("thresholds")
    if not isinstance(thresholds_payload, dict):
        raise ValueError("Prescreen scoring config field 'thresholds' must be an object")

    score_min = _require_non_negative_int(thresholds_payload, "score_min")
    score_max = _require_non_negative_int(thresholds_payload, "score_max")
    tier_a_min = _require_non_negative_int(thresholds_payload, "tier_a_min")
    tier_b_min = _require_non_negative_int(thresholds_payload, "tier_b_min")

    if score_min > score_max:
        raise ValueError("Prescreen scoring config thresholds must satisfy score_min <= score_max")
    if tier_b_min > tier_a_min:
        raise ValueError("Prescreen scoring config thresholds must satisfy tier_b_min <= tier_a_min")

    return {
        "negative_signal_keywords": negative_signal_keywords,
        "negative_interest_keywords": negative_interest_keywords,
        "evidence_fields": evidence_fields,
        "title_keywords": {
            "senior": senior_title_keywords,
            "mid": mid_title_keywords,
        },
        "weights": weights,
        "thresholds": {
            "score_min": score_min,
            "score_max": score_max,
            "tier_a_min": tier_a_min,
            "tier_b_min": tier_b_min,
        },
    }


def load_contacted_teachers(path: Path) -> Dict[str, set[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Contacted teachers file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Contacted teachers file must be a JSON object")

    schools = payload.get("schools")
    if not isinstance(schools, list):
        raise ValueError("Contacted teachers file missing 'schools' array")

    result: Dict[str, set[str]] = {}
    for index, item in enumerate(schools):
        if not isinstance(item, dict):
            raise ValueError(f"Contacted schools[{index}] must be an object")

        school = normalize_text(str(item.get("school", "")))
        if not school:
            raise ValueError(f"Contacted schools[{index}].school is required")

        entries = item.get("entries")
        if not isinstance(entries, list):
            raise ValueError(f"Contacted schools[{index}].entries must be an array")

        names: set[str] = set()
        for entry_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValueError(f"Contacted schools[{index}].entries[{entry_index}] must be an object")

            name = normalize_text(str(entry.get("name", "")))
            if not name:
                raise ValueError(f"Contacted schools[{index}].entries[{entry_index}].name is required")
            names.add(re.sub(r"\s+", "", name))

        result[school] = names

    return result


def parse_keyword_csv(value: str) -> List[str]:
    if not normalize_text(value):
        return []

    items = [normalize_text(item) for item in value.split(",")]
    deduped: List[str] = []
    seen = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _normalize_profile_name(value: str) -> str:
    name = normalize_text(value)
    if CHINESE_NAME_PATTERN.fullmatch(re.sub(r"\s+", "", name)):
        return re.sub(r"\s+", "", name)
    return normalize_spaces(name)


def _validate_prescreen_profile(profile: object, index: int) -> Dict[str, object]:
    if not isinstance(profile, dict):
        raise ValueError(f"teacher_profiles[{index}] must be an object")

    raw_name = profile.get("name")
    if not isinstance(raw_name, str) or not normalize_text(raw_name):
        raise ValueError(f"teacher_profiles[{index}].name is required")

    raw_interests = profile.get("interests", [])
    if not isinstance(raw_interests, list):
        raise ValueError(f"teacher_profiles[{index}].interests must be an array")

    normalized = dict(profile)
    normalized["name"] = _normalize_profile_name(raw_name)
    normalized["profile_url"] = profile.get("profile_url") if isinstance(profile.get("profile_url"), str) else None
    normalized["email"] = normalize_text(str(profile.get("email", ""))).lower() if profile.get("email") else None
    normalized["title"] = normalize_text(str(profile.get("title", ""))) if profile.get("title") else None
    normalized["source_url"] = normalize_text(str(profile.get("source_url", ""))) if profile.get("source_url") else ""
    normalized["interests"] = [normalize_text(str(item)) for item in raw_interests if normalize_text(str(item))]
    return normalized


def _has_negative_signal_evidence(
    profile: Dict[str, object],
    negative_keywords: List[str],
    evidence_fields: List[str],
) -> bool:
    evidence_chunks = [
        normalize_spaces(str(profile.get(field, "")))
        for field in evidence_fields
        if isinstance(profile.get(field), str) and normalize_text(str(profile.get(field)))
    ]
    if not evidence_chunks:
        return False

    evidence_text = " ".join(evidence_chunks).lower()
    for keyword in negative_keywords:
        if keyword.lower() in evidence_text:
            return True
    return False


def _is_whole_word_match(text: str, keyword: str) -> bool:
    if not text or not keyword:
        return False
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    if keyword.isascii():
        pattern = r"\b" + re.escape(keyword_lower) + r"\b"
        return bool(re.search(pattern, text_lower))
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(keyword_lower) + r"(?![a-zA-Z0-9])"
    return bool(re.search(pattern, text_lower))


def _match_keywords_in_fields(fields: List[str], keywords: List[str]) -> List[str]:
    matched: List[str] = []
    for keyword in keywords:
        for field in fields:
            if field and _is_whole_word_match(field, keyword):
                matched.append(keyword)
                break
    return list(dict.fromkeys(matched))


def _score_teacher_profile(
    profile: Dict[str, object],
    keywords: List[str],
    scoring_config: Dict[str, Any],
    negative_keywords: List[str],
) -> tuple[int, str, List[str], List[str], List[str]]:
    score = 0
    reasons: List[str] = []
    weights = scoring_config["weights"]
    title_keywords = scoring_config["title_keywords"]
    thresholds = scoring_config["thresholds"]

    profile_url = profile.get("profile_url")
    if profile_url:
        score += int(weights["profile_url_bonus"])
        reasons.append("has_profile_url")
        if looks_like_profile_url(str(profile_url)):
            score += int(weights["profile_url_person_like_bonus"])
            reasons.append("profile_url_person_like")
    else:
        score -= int(weights["missing_profile_url_penalty"])
        reasons.append("missing_profile_url")

    if profile.get("email"):
        score += int(weights["has_email_bonus"])
        reasons.append("has_email")
    else:
        score -= int(weights["missing_email_penalty"])
        reasons.append("missing_email")

    title = str(profile.get("title") or "")
    if title:
        if any(keyword in title for keyword in title_keywords["senior"]):
            score += int(weights["senior_title_bonus"])
            reasons.append("senior_title")
        elif any(keyword in title for keyword in title_keywords["mid"]):
            score += int(weights["mid_title_bonus"])
            reasons.append("title_signal")
        else:
            score += int(weights["other_title_bonus"])
            reasons.append("has_title")
    else:
        reasons.append("missing_title")

    interests = [normalize_text(str(item)) for item in profile.get("interests", []) if normalize_text(str(item))]
    if interests:
        score += int(weights["has_interests_bonus"])
        reasons.append("has_interests")
    else:
        score -= int(weights["missing_interests_penalty"])
        reasons.append("missing_interests")

    search_fields: List[str] = [title, *interests]
    homepage = profile.get("homepage")
    if isinstance(homepage, dict):
        for field in ("research_fields", "bio", "representative_works", "conferences"):
            val = homepage.get(field)
            if isinstance(val, list):
                search_fields.extend(str(v) for v in val if str(v))
            elif isinstance(val, str) and val:
                search_fields.append(val)

    matched_keywords: List[str] = []
    if keywords:
        matched_keywords = _match_keywords_in_fields(search_fields, keywords)
        if matched_keywords:
            score += min(
                int(weights["keyword_match_bonus_cap"]),
                len(matched_keywords) * int(weights["keyword_match_per_hit_bonus"]),
            )
            reasons.append(f"keyword_match:{'|'.join(matched_keywords)}")
        else:
            reasons.append("keyword_miss")

    matched_negative_keywords: List[str] = []
    if negative_keywords:
        matched_negative_keywords = _match_keywords_in_fields(search_fields, negative_keywords)
        if matched_negative_keywords:
            penalty = min(
                int(weights["negative_keyword_match_penalty_cap"]),
                len(matched_negative_keywords) * int(weights["negative_keyword_match_per_hit_penalty"]),
            )
            score -= penalty
            reasons.append(f"negative_keyword_match:{'|'.join(matched_negative_keywords)}")
        else:
            reasons.append("negative_keyword_miss")

    if interests and not matched_keywords and not matched_negative_keywords:
        score -= int(weights["neutral_penalty"])
        reasons.append("neutral_penalty")

    final_score = max(int(thresholds["score_min"]), min(int(thresholds["score_max"]), score))
    tier = "A" if final_score >= int(thresholds["tier_a_min"]) else "B" if final_score >= int(thresholds["tier_b_min"]) else "C"
    return final_score, tier, reasons, matched_keywords, matched_negative_keywords


def run_offline_prescreen(
    payload: Dict[str, object],
    *,
    top_n: int,
    budget: int,
    keywords: List[str],
    contacted_teachers: Dict[str, set[str]],
    negative_signal_keywords: Optional[List[str]] = None,
    negative_keywords: Optional[List[str]] = None,
    scoring_config_path: Optional[Path] = None,
) -> Dict[str, object]:
    if top_n <= 0:
        raise ValueError("top_n must be > 0")
    if budget <= 0:
        raise ValueError("budget must be > 0")

    school = normalize_text(str(payload.get("school", "")))
    college = normalize_text(str(payload.get("college", "")))
    source_url = normalize_text(str(payload.get("url", "")))
    if not school or not college or not source_url:
        raise ValueError("Prescreen payload missing school/college/url")

    raw_profiles = payload.get("teacher_profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("Prescreen payload missing teacher_profiles array")

    scoring_config = load_prescreen_scoring_config(scoring_config_path or DEFAULT_PRESCREEN_SCORING_CONFIG_PATH)
    evidence_negative_keywords = negative_signal_keywords or list(scoring_config["negative_signal_keywords"])
    interest_negative_keywords = negative_keywords or list(scoring_config.get("negative_interest_keywords", []))
    evidence_fields = list(scoring_config["evidence_fields"])
    contacted_names = contacted_teachers.get(school, set())

    eligible_items: List[Dict[str, object]] = []
    skipped_items: List[Dict[str, object]] = []
    tier_counter = {"A": 0, "B": 0, "C": 0}

    for index, raw_profile in enumerate(raw_profiles):
        profile = _validate_prescreen_profile(raw_profile, index=index)
        teacher_name = str(profile["name"])
        compact_name = re.sub(r"\s+", "", teacher_name)

        if compact_name in contacted_names:
            skipped_items.append(
                {
                    "name": teacher_name,
                    "score": 0,
                    "tier": "C",
                    "reasons": ["already_contacted"],
                    "matched_keywords": [],
                    "matched_negative_keywords": [],
                    "skip_reason": "already_contacted",
                    "profile": profile,
                }
            )
            continue

        if _has_negative_signal_evidence(profile, evidence_negative_keywords, evidence_fields):
            skipped_items.append(
                {
                    "name": teacher_name,
                    "score": 0,
                    "tier": "C",
                    "reasons": ["negative_signal_evidence"],
                    "matched_keywords": [],
                    "matched_negative_keywords": [],
                    "skip_reason": "negative_signal_evidence",
                    "profile": profile,
                }
            )
            continue

        score, tier, reasons, matched_keywords, matched_negative_keywords = _score_teacher_profile(
            profile,
            keywords=keywords,
            scoring_config=scoring_config,
            negative_keywords=interest_negative_keywords,
        )
        tier_counter[tier] += 1
        eligible_items.append(
            {
                "name": teacher_name,
                "score": score,
                "tier": tier,
                "reasons": reasons,
                "matched_keywords": matched_keywords,
                "matched_negative_keywords": matched_negative_keywords,
                "skip_reason": None,
                "profile": profile,
            }
        )

    ranked = sorted(eligible_items, key=lambda item: (-int(item["score"]), str(item["name"])))
    selected_count = min(top_n, budget, len(ranked))
    top_candidates: List[Dict[str, object]] = []

    for index, item in enumerate(ranked):
        candidate = dict(item)
        candidate["rank"] = index + 1
        if index < selected_count:
            candidate["selected"] = True
            top_candidates.append(candidate)
        else:
            candidate["selected"] = False
            candidate["skip_reason"] = "over_budget"
            skipped_items.append(candidate)
        ranked[index] = candidate

    already_contacted_skipped = sum(1 for item in skipped_items if item.get("skip_reason") == "already_contacted")
    negative_signal_skipped = sum(1 for item in skipped_items if item.get("skip_reason") == "negative_signal_evidence")
    over_budget_skipped = sum(1 for item in skipped_items if item.get("skip_reason") == "over_budget")

    return {
        "school": school,
        "college": college,
        "url": source_url,
        "top_n": top_n,
        "budget": budget,
        "keywords": keywords,
        "negative_keywords": interest_negative_keywords,
        "stats": {
            "total_profiles": len(raw_profiles),
            "scored_profiles": len(ranked),
            "selected_profiles": len(top_candidates),
            "skipped_profiles": len(skipped_items),
            "already_contacted_skipped": already_contacted_skipped,
            "negative_signal_skipped": negative_signal_skipped,
            "over_budget_skipped": over_budget_skipped,
            "tier_distribution": tier_counter,
        },
        "top_candidates": top_candidates,
        "candidates": ranked,
        "skipped": skipped_items,
    }
