# LLM Pipeline Design Spec

## Overview

Replace regex-based extraction and rule-based scoring with LLM-powered information extraction and matching, using DeepSeek-V3.2 via SiliconFlow API.

## Pipeline

```
Step1  Teacher list collection (existing, unchanged)
  └── Output: teachers.json [name, profile_url, ...]

Step2  Profile page scraping (existing, unchanged)
  └── Scrape profile_url → clean text → full_text
  └── Output: enriched teachers.json (with full_text, homepage, etc.)

Step3  LLM information extraction (NEW)
  ├── Read full_text per teacher
  ├── Call DeepSeek-V3.2 to extract structured JSON (basic layer)
  ├── If homepage_url exists, scrape homepage → full_text_homepage → second LLM call (extended layer)
  └── Output: llm_enriched teachers.json

Step4  LLM matching recommendation (NEW)
  ├── Read llm_enriched teachers.json
  ├── Read user input (resume + research interests)
  ├── Pre-filter top 100-200 by keyword match
  ├── Call LLM per candidate for match assessment
  └── Output: recommendations.json
```

## Module Structure

```
src/llm/
├── __init__.py
├── llm_client.py          # SiliconFlow API wrapper (OpenAI-compatible)
├── profile_extractor.py   # Step3: LLM extract teacher info
├── match_engine.py        # Step4: LLM match recommendation
└── prompts.py             # All prompt constants
```

### llm_client.py

- Wraps SiliconFlow OpenAI-compatible API
- Model: `deepseek-ai/DeepSeek-V3`
- Method: `extract_structured(prompt, text) -> dict`
- Retry: 2 retries on network failure (consistent with scholar_client)
- API key: `SILICONFLOW_API_KEY` env var, missing = raise immediately

### profile_extractor.py

- Input: teachers.json list
- Per teacher: call LLM with full_text (basic layer); if homepage_url, call LLM with homepage text (extended layer)
- Output: llm_enriched teachers.json (original fields + llm_basic + llm_extended)

### match_engine.py

- Input: llm_enriched teachers.json + user resume + research interests
- Pre-filter top 100-200 by keyword matching, then LLM assesses each
- Output: recommendations.json (match_score + match_reasons + risk_flags)

### prompts.py

- `PROFILE_EXTRACT_PROMPT` — basic layer extraction
- `HOMEPAGE_EXTRACT_PROMPT` — extended layer extraction
- `MATCH_PROMPT` — match recommendation

## Extraction Schemas

### Basic Layer (from school profile full_text)

```json
{
  "title": "教授",
  "email": "xxx@xxx.edu.cn",
  "homepage_url": "https://...",
  "google_scholar_url": null,
  "github_url": null,
  "research_keywords": ["NLP", "机器学习"],
  "bio": "一段话简介",
  "is_phd_supervisor": true,
  "is_master_supervisor": true
}
```

Rules: extract only from text, never fabricate; all fields nullable; research_keywords from page content, not LLM-generated.

### Extended Layer (from homepage full_text)

```json
{
  "research_summary": "LLM 综合归纳 2-4 句话",
  "recruiting_status": "active|unknown|not_recruiting",
  "recruiting_targets": ["phd", "master"],
  "recruiting_note": "原文摘录",
  "recent_works": [
    {"title": "...", "venue": "NeurIPS 2025", "year": 2025, "citation_count": 40}
  ],
  "lab_name": "DeepDelta Lab",
  "awards": ["ICLR 2025 Outstanding Paper"],
  "conference_roles": ["NeurIPS 2025 Area Chair"],
  "open_source_projects": ["FCOS"]
}
```

Rules: research_summary is the only summarization field (2-4 sentences); recruiting_status conservative (unknown if unclear); recent_works only 3-5 representative papers.

### Match Output

```json
{
  "match_score": 85,
  "match_reasons": ["方向高度匹配：...", "导师正在招生：..."],
  "risk_flags": ["研究方向可能偏理论"]
}
```

Rules: strict prompts, prefer false negatives over false positives.

## Batch Processing

- Sequential processing (avoid API rate limits)
- 0.5s sleep between calls (configurable)
- Progress: `[42/1480] Processing 张三...`
- Single-teacher failure does not block batch; log error and continue
- Incremental save: write to output file after each teacher (crash-safe)

## CLI

```bash
# Step3: LLM extraction
python src/llm/profile_extractor.py \
  --input output/清华大学/teachers.json \
  --output output/清华大学/llm_enriched.json

# Step4: LLM matching
python src/llm/match_engine.py \
  --input output/清华大学/llm_enriched.json \
  --resume data/my_resume.txt \
  --interests data/my_interests.txt \
  --output output/清华大学/recommendations.json
```

## Dependencies

- New: `openai>=1.0.0` (SiliconFlow uses OpenAI-compatible API)

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Scraper framework | Keep requests+regex | Sufficient for current sites, avoid heavy deps |
| LLM provider | DeepSeek-V3.2 via SiliconFlow | Cost-effective for ~15M tokens |
| API auth | `SILICONFLOW_API_KEY` env var | Standard practice |
| Architecture | Independent `src/llm/` module | Decouple LLM from scraping |
| Prompt management | Inline in `prompts.py` | Project scale doesn't warrant external files |
| Batch strategy | Full extraction then match | Reusable, auditable intermediate results |
| Google Scholar | Not used for matching | Per user decision (Q6=A) |
| Match input | Resume + research interests | Per user decision (Q5) |
