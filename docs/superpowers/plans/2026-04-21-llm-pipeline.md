# LLM Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-powered information extraction and teacher matching using DeepSeek-V3.2 via SiliconFlow API.

**Architecture:** New `src/llm/` module with four files: API client wrapper, prompt constants, profile extractor (Step3), and match engine (Step4). The existing scraping pipeline is untouched; LLM reads the already-cleaned `full_text` from teachers.json.

**Tech Stack:** `openai` Python SDK (SiliconFlow is OpenAI-compatible), existing `utils.py` for logging.

---

### Task 1: Add `openai` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add openai to requirements.txt**

```txt
requests>=2.32.0
python-dotenv>=1.0.0
pypinyin>=0.54.0
openai>=1.0.0
```

- [ ] **Step 2: Install dependency**

Run: `pip install -r requirements.txt`
Expected: installs openai without errors

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add openai dependency for SiliconFlow API"
```

---

### Task 2: Create `src/llm/` module with `llm_client.py`

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write `src/llm/__init__.py`**

```python
```

- [ ] **Step 2: Write `tests/test_llm_client.py`**

```python
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm.llm_client import LLMClient


class TestLLMClientInit(unittest.TestCase):
    def test_raises_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                LLMClient()
            self.assertIn("SILICONFLOW_API_KEY", str(ctx.exception))

    def test_init_with_api_key(self):
        with patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"}):
            client = LLMClient()
            self.assertEqual(client.model, "deepseek-ai/DeepSeek-V3")


class TestLLMClientExtract(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_extract_structured_returns_parsed_json(self):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({"title": "教授", "email": "a@b.edu.cn"}, ensure_ascii=False)
                )
            )
        ]

        with patch("llm.llm_client.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = mock_response

            client = LLMClient()
            result = client.extract_structured(
                system_prompt="Extract info",
                user_text="张三，教授，邮箱 a@b.edu.cn",
            )

            self.assertEqual(result["title"], "教授")
            self.assertEqual(result["email"], "a@b.edu.cn")

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_extract_structured_handles_malformed_json(self):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not json at all"))
        ]

        with patch("llm.llm_client.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.return_value = mock_response

            client = LLMClient()
            with self.assertRaises(ValueError) as ctx:
                client.extract_structured("prompt", "text")
            self.assertIn("JSON", str(ctx.exception))

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_extract_structured_retries_on_connection_error(self):
        import openai

        call_count = {"n": 0}
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"title": "教授"}'))
        ]

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise openai.APIConnectionError("connection failed")
            return mock_response

        with patch("llm.llm_client.OpenAI") as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.chat.completions.create.side_effect = side_effect

            client = LLMClient()
            result = client.extract_structured("prompt", "text")
            self.assertEqual(result["title"], "教授")
            self.assertEqual(call_count["n"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Write `src/llm/llm_client.py`**

```python
#!/usr/bin/env python3
"""SiliconFlow API wrapper using OpenAI-compatible SDK."""

from __future__ import annotations

import json
import os

import openai
from openai import OpenAI

from utils import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
MAX_RETRIES = 2  # total attempts = MAX_RETRIES + 1 = 3


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
    ):
        key = api_key or os.environ.get("SILICONFLOW_API_KEY")
        if not key:
            raise RuntimeError("Missing environment variable: SILICONFLOW_API_KEY")
        self.model = model
        self.client = OpenAI(
            api_key=key,
            base_url=base_url,
            max_retries=0,  # we handle retries ourselves
        )

    def extract_structured(self, system_prompt: str, user_text: str) -> dict:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text},
                    ],
                    temperature=0.0,
                )
                raw = response.choices[0].message.content
                if not raw:
                    raise ValueError("LLM returned empty content")
                return json.loads(raw)
            except (openai.APIConnectionError, openai.APITimeoutError) as exc:
                if attempt < MAX_RETRIES:
                    logger.warning("LLM request failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES + 1, exc)
                    continue
                raise
            except json.JSONDecodeError as exc:
                raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
        raise RuntimeError("unreachable")
```

- [ ] **Step 4: Run tests to verify**

Run: `cd /Users/kalin/github/baoyan_search_teachar && python -m pytest tests/test_llm_client.py -v`
Expected: 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/llm/__init__.py src/llm/llm_client.py tests/test_llm_client.py
git commit -m "feat: add LLM client for SiliconFlow API with retry and JSON parsing"
```

---

### Task 3: Create `src/llm/prompts.py` — all prompt constants

**Files:**
- Create: `src/llm/prompts.py`

- [ ] **Step 1: Write prompts**

```python
#!/usr/bin/env python3
"""Prompt templates for LLM extraction and matching."""

from __future__ import annotations

BASIC_EXTRACT_PROMPT = """\
你是一个信息提取助手。从下面的教师学校主页文本中提取结构化信息。

规则：
1. 只从文本中提取信息，不要编造或推测任何内容
2. 所有字段都是可选的，如果文本中没有相关信息，填 null
3. research_keywords 从页面列出的研究方向提取，不要自己生成
4. bio 从页面"个人简介"字段提取原文，若页面无内容则填 null
5. is_phd_supervisor / is_master_supervisor 从页面标注（如"博士生导师"）判断，无标注则填 false

输出 JSON，字段如下：
{
  "title": "职称，如教授、副教授、助理教授、研究员等",
  "email": "邮箱地址",
  "homepage_url": "个人主页URL",
  "google_scholar_url": "Google Scholar链接",
  "github_url": "GitHub链接",
  "research_keywords": ["3-8个研究方向关键词"],
  "bio": "个人简介原文，一段话",
  "is_phd_supervisor": false,
  "is_master_supervisor": false
}

只输出 JSON，不要输出其他内容。"""

EXTENDED_EXTRACT_PROMPT = """\
你是一个信息提取助手。从下面的教师个人主页文本中提取结构化信息。

规则：
1. 只从文本中提取信息，不要编造或推测任何内容
2. 所有字段都是可选的，如果文本中没有相关信息，填 null
3. research_summary 是唯一需要你总结的字段：基于全文综合归纳 2-4 句话，突出研究主线和近年方向
4. recruiting_status 枚举值：active（明确在招生）/ unknown（无明确信息）/ not_recruiting（明确不招）
5. recent_works 只取 3-5 篇代表作，优先近2年+高引用+顶会；citation_count 无则填 null
6. recruiting_targets 从 ["phd", "master", "postdoc", "intern", "ra"] 中选零、一个或者多个

输出 JSON，字段如下：
{
  "research_summary": "研究主线和近年方向的综合归纳，2-4句话",
  "recruiting_status": "active 或 unknown 或 not_recruiting",
  "recruiting_targets": ["phd", "master"],
  "recruiting_note": "招生相关原文摘录",
  "recent_works": [
    {"title": "论文标题", "venue": "NeurIPS 2025", "year": 2025, "citation_count": 40}
  ],
  "lab_name": "实验室名称",
  "awards": ["重要奖项"],
  "conference_roles": ["学术服务角色，如 Area Chair"],
  "open_source_projects": ["开源项目名称"]
}

只输出 JSON，不要输出其他内容。"""

MATCH_PROMPT = """\
你是一个研究生导师匹配助手。根据教师信息和学生的背景，评估匹配度。

评估标准（严格）：
1. 研究方向匹配度：学生的研究兴趣和导师的研究方向是否高度一致
2. 招生状态：导师是否在招生（recruiting_status 为 active 或 unknown）
3. 导师水平：基于论文发表、奖项、学术服务等判断
4. 风险因素：方向可能偏理论/偏工程、导师可能已不招生、信息缺失等

打分规则：
- 90+：研究方向高度匹配，导师明确在招，学术水平高
- 70-89：研究方向匹配，但可能有一些不确定性
- 50-69：方向有一定相关性，但匹配度不高
- <50：不太匹配

宁缺毋滥，不确定时打低分。

输出 JSON：
{
  "match_score": 85,
  "match_reasons": ["匹配理由1", "匹配理由2"],
  "risk_flags": ["风险因素1"]
}

只输出 JSON，不要输出其他内容。"""

- [ ] **Step 2: Commit**

```bash
git add src/llm/prompts.py
git commit -m "feat: add LLM prompt templates for extraction and matching"
```

---

### Task 4: Create `src/llm/profile_extractor.py` — Step3 batch extraction

**Files:**
- Create: `src/llm/profile_extractor.py`
- Create: `tests/test_profile_extractor.py`

- [ ] **Step 1: Write `tests/test_profile_extractor.py`**

```python
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm.profile_extractor import extract_one_profile, run_extraction


class TestExtractOneProfile(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_basic_extraction_from_full_text(self):
        basic_result = {
            "title": "教授",
            "email": "zhang@tsinghua.edu.cn",
            "research_keywords": ["NLP", "深度学习"],
            "bio": "清华大学计算机系教授",
            "is_phd_supervisor": True,
            "is_master_supervisor": True,
            "homepage_url": None,
            "google_scholar_url": None,
            "github_url": None,
        }

        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_structured.return_value = basic_result

            teacher = {
                "name": "张三",
                "profile_url": "https://example.com/zhangsan",
                "homepage": {"full_text": "张三，教授，NLP与深度学习。博士生导师。邮箱zhang@tsinghua.edu.cn"},
            }

            result = extract_one_profile(mock_instance, teacher)

            self.assertEqual(result["name"], "张三")
            self.assertEqual(result["llm_basic"]["title"], "教授")
            self.assertEqual(result["llm_basic"]["email"], "zhang@tsinghua.edu.cn")
            self.assertIsNone(result["llm_extended"])

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_extended_extraction_when_homepage_url_exists(self):
        basic_result = {"title": "教授", "email": None, "research_keywords": [], "bio": None, "is_phd_supervisor": False, "is_master_supervisor": False, "homepage_url": "https://example.com", "google_scholar_url": None, "github_url": None}
        extended_result = {
            "research_summary": "研究NLP和深度学习",
            "recruiting_status": "active",
            "recruiting_targets": ["phd"],
            "recruiting_note": None,
            "recent_works": [],
            "lab_name": None,
            "awards": [],
            "conference_roles": [],
            "open_source_projects": [],
        }

        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_structured.side_effect = [basic_result, extended_result]

            with patch("llm.profile_extractor.fetch_homepage_text") as mock_fetch:
                mock_fetch.return_value = "个人主页内容"

                teacher = {
                    "name": "李四",
                    "profile_url": "https://example.com/lisi",
                    "homepage": {
                        "full_text": "李四，教授",
                        "personal_homepage": "https://personal.example.com",
                    },
                }

                result = extract_one_profile(mock_instance, teacher)
                self.assertEqual(result["llm_extended"]["recruiting_status"], "active")
                self.assertEqual(mock_instance.extract_structured.call_count, 2)

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_single_failure_does_not_block(self):
        with patch("llm.profile_extractor.LLMClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.extract_structured.side_effect = RuntimeError("API error")

            teacher = {
                "name": "王五",
                "profile_url": "https://example.com/wangwu",
                "homepage": {"full_text": "王五信息"},
            }

            result = extract_one_profile(mock_instance, teacher)
            self.assertEqual(result["name"], "王五")
            self.assertIsNone(result["llm_basic"])
            self.assertIn("error", result)

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_skips_when_no_full_text(self):
        with patch("llm.profile_extractor.LLMClient") as MockClient:
            teacher = {
                "name": "赵六",
                "profile_url": "https://example.com/zhaoliu",
            }

            result = extract_one_profile(mock_instance, teacher)
            self.assertEqual(result["name"], "赵六")
            self.assertIsNone(result["llm_basic"])
            self.assertEqual(result.get("skip_reason"), "no_full_text")


class TestRunExtraction(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_batch_writes_incrementally(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "teachers.json"
            output_path = Path(tmpdir) / "llm_enriched.json"

            input_data = {
                "school": "清华大学",
                "college": "计算机系",
                "teacher_profiles": [
                    {"name": "甲", "profile_url": "https://a.com", "homepage": {"full_text": "甲信息"}},
                    {"name": "乙", "profile_url": "https://b.com", "homepage": {"full_text": "乙信息"}},
                ],
            }
            input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")

            with patch("llm.profile_extractor.LLMClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.extract_structured.return_value = {
                    "title": "教授", "email": None, "research_keywords": [],
                    "bio": None, "is_phd_supervisor": False, "is_master_supervisor": False,
                    "homepage_url": None, "google_scholar_url": None, "github_url": None,
                }

                run_extraction(str(input_path), str(output_path))

            output = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(output["teacher_profiles"]), 2)
            self.assertIsNotNone(output["teacher_profiles"][0]["llm_basic"])
            self.assertIsNotNone(output["teacher_profiles"][1]["llm_basic"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write `src/llm/profile_extractor.py`**

```python
#!/usr/bin/env python3
"""Step3: LLM-powered teacher profile extraction (basic + extended layers)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from utils import configure_logging, get_logger

from llm.llm_client import LLMClient
from llm.prompts import BASIC_EXTRACT_PROMPT, EXTENDED_EXTRACT_PROMPT

logger = get_logger(__name__)

DEFAULT_DELAY = 0.5


def _get_full_text(teacher: Dict[str, Any]) -> Optional[str]:
    homepage = teacher.get("homepage")
    if isinstance(homepage, dict):
        return homepage.get("full_text")
    return None


def _get_homepage_url(teacher: Dict[str, Any]) -> Optional[str]:
    homepage = teacher.get("homepage")
    if isinstance(homepage, dict):
        return homepage.get("personal_homepage")
    return None


def fetch_homepage_text(url: str, timeout: int = 30) -> str:
    import re
    from html import unescape

    import requests

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = unescape(text)
    lines = [line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 2]
    return "\n".join(lines)


def extract_one_profile(client: LLMClient, teacher: Dict[str, Any]) -> Dict[str, Any]:
    result = {"name": teacher["name"]}

    full_text = _get_full_text(teacher)
    if not full_text:
        result["skip_reason"] = "no_full_text"
        return result

    try:
        basic = client.extract_structured(BASIC_EXTRACT_PROMPT, full_text)
        result["llm_basic"] = basic
    except Exception as exc:
        logger.warning("LLM basic extraction failed for %s: %s", teacher["name"], exc)
        result["error"] = str(exc)
        return result

    homepage_url = _get_homepage_url(teacher)
    if homepage_url:
        try:
            homepage_text = fetch_homepage_text(homepage_url)
            if homepage_text:
                extended = client.extract_structured(EXTENDED_EXTRACT_PROMPT, homepage_text)
                result["llm_extended"] = extended
        except Exception as exc:
            logger.warning("LLM extended extraction failed for %s: %s", teacher["name"], exc)
            result["llm_extended_error"] = str(exc)

    return result


def run_extraction(
    input_path: str,
    output_path: str,
    delay: float = DEFAULT_DELAY,
) -> Dict[str, int]:
    client = LLMClient()
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    profiles = data.get("teacher_profiles", [])

    stats = {"total": len(profiles), "success": 0, "skipped": 0, "failed": 0}
    results = []

    for i, teacher in enumerate(profiles):
        name = teacher["name"]
        logger.info("[%d/%d] Processing %s...", i + 1, len(profiles), name)

        result = extract_one_profile(client, teacher)

        if result.get("skip_reason"):
            stats["skipped"] += 1
        elif result.get("error"):
            stats["failed"] += 1
        else:
            stats["success"] += 1

        merged = {**teacher, **result}
        results.append(merged)

        data["teacher_profiles"] = results
        Path(output_path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if i < len(profiles) - 1:
            time.sleep(delay)

    logger.info("Extraction complete: %s", stats)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-powered teacher profile extraction")
    parser.add_argument("--input", required=True, help="Input teachers.json path")
    parser.add_argument("--output", required=True, help="Output llm_enriched.json path")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between API calls")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)
    stats = run_extraction(args.input, args.output, delay=args.delay)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/kalin/github/baoyan_search_teachar && python -m pytest tests/test_profile_extractor.py -v`
Expected: 5 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/llm/profile_extractor.py tests/test_profile_extractor.py
git commit -m "feat: add LLM profile extractor with batch processing and incremental save"
```

---

### Task 5: Create `src/llm/match_engine.py` — Step4 matching

**Files:**
- Create: `src/llm/match_engine.py`
- Create: `tests/test_match_engine.py`

- [ ] **Step 1: Write `tests/test_match_engine.py`**

```python
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm.match_engine import run_matching


class TestRunMatching(unittest.TestCase):
    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_matches_teachers_and_outputs_recommendations(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "llm_enriched.json"
            resume_path = Path(tmpdir) / "resume.txt"
            interests_path = Path(tmpdir) / "interests.txt"
            output_path = Path(tmpdir) / "recommendations.json"

            input_data = {
                "school": "清华大学",
                "college": "计算机系",
                "teacher_profiles": [
                    {
                        "name": "甲",
                        "llm_basic": {"research_keywords": ["NLP", "深度学习"]},
                    },
                    {
                        "name": "乙",
                        "llm_basic": {"research_keywords": ["计算机视觉"]},
                    },
                ],
            }
            input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")
            resume_path.write_text("我是计算机系本科生，对NLP感兴趣", encoding="utf-8")
            interests_path.write_text("自然语言处理、大语言模型、深度学习", encoding="utf-8")

            def mock_extract(system_prompt, user_text):
                if "甲" in user_text:
                    return {"match_score": 85, "match_reasons": ["研究方向高度匹配"], "risk_flags": []}
                return {"match_score": 40, "match_reasons": ["方向不太相关"], "risk_flags": ["方向不匹配"]}

            with patch("llm.match_engine.LLMClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.extract_structured.side_effect = mock_extract

                stats = run_matching(
                    str(input_path),
                    str(resume_path),
                    str(interests_path),
                    str(output_path),
                )

            self.assertEqual(stats["total"], 2)

            output = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(output["recommendations"]), 2)

            rec_jia = output["recommendations"][0]
            self.assertEqual(rec_jia["teacher"], "甲")
            self.assertEqual(rec_jia["match_score"], 85)

    @patch.dict("os.environ", {"SILICONFLOW_API_KEY": "test-key"})
    def test_failure_per_teacher_does_not_block_batch(self):
        with TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "llm_enriched.json"
            resume_path = Path(tmpdir) / "resume.txt"
            interests_path = Path(tmpdir) / "interests.txt"
            output_path = Path(tmpdir) / "recommendations.json"

            input_data = {
                "school": "清华大学",
                "college": "计算机系",
                "teacher_profiles": [
                    {"name": "甲", "llm_basic": {"research_keywords": ["NLP"]}},
                ],
            }
            input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")
            resume_path.write_text("简历", encoding="utf-8")
            interests_path.write_text("NLP", encoding="utf-8")

            with patch("llm.match_engine.LLMClient") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.extract_structured.side_effect = RuntimeError("API error")

                stats = run_matching(
                    str(input_path),
                    str(resume_path),
                    str(interests_path),
                    str(output_path),
                )

            self.assertEqual(stats["total"], 1)
            self.assertEqual(stats["failed"], 1)

            output = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(output["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write `src/llm/match_engine.py`**

```python
#!/usr/bin/env python3
"""Step4: LLM-powered teacher matching and recommendation."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from utils import configure_logging, get_logger

from llm.llm_client import LLMClient
from llm.prompts import MATCH_PROMPT

logger = get_logger(__name__)

DEFAULT_DELAY = 0.5


def _build_teacher_summary(teacher: Dict[str, Any]) -> str:
    parts = [f"姓名: {teacher['name']}"]

    basic = teacher.get("llm_basic")
    if basic:
        if basic.get("title"):
            parts.append(f"职称: {basic['title']}")
        if basic.get("research_keywords"):
            parts.append(f"研究方向: {'、'.join(basic['research_keywords'])}")
        if basic.get("bio"):
            parts.append(f"简介: {basic['bio']}")

    extended = teacher.get("llm_extended")
    if extended:
        if extended.get("research_summary"):
            parts.append(f"研究总结: {extended['research_summary']}")
        if extended.get("recruiting_status"):
            parts.append(f"招生状态: {extended['recruiting_status']}")
        if extended.get("recruiting_targets"):
            parts.append(f"招生类型: {', '.join(extended['recruiting_targets'])}")
        if extended.get("recent_works"):
            works = [f"- {w['title']} ({w.get('venue', '')}, {w.get('year', '')})" for w in extended["recent_works"]]
            parts.append("代表作:\n" + "\n".join(works))
        if extended.get("awards"):
            parts.append(f"奖项: {'、'.join(extended['awards'])}")

    return "\n".join(parts)


def run_matching(
    input_path: str,
    resume_path: str,
    interests_path: str,
    output_path: str,
    delay: float = DEFAULT_DELAY,
) -> Dict[str, int]:
    client = LLMClient()
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    resume = Path(resume_path).read_text(encoding="utf-8").strip()
    interests = Path(interests_path).read_text(encoding="utf-8").strip()
    profiles = data.get("teacher_profiles", [])

    user_context = f"## 我的简历\n{resume}\n\n## 我的研究兴趣\n{interests}"

    stats = {"total": len(profiles), "matched": 0, "failed": 0}
    recommendations: List[Dict[str, Any]] = []

    for i, teacher in enumerate(profiles):
        name = teacher["name"]
        logger.info("[%d/%d] Matching %s...", i + 1, len(profiles), name)

        teacher_summary = _build_teacher_summary(teacher)
        user_prompt = f"## 教师信息\n{teacher_summary}\n\n{user_context}"

        try:
            result = client.extract_structured(MATCH_PROMPT, user_prompt)
            rec = {
                "teacher": name,
                "match_score": result.get("match_score", 0),
                "match_reasons": result.get("match_reasons", []),
                "risk_flags": result.get("risk_flags", []),
            }
            recommendations.append(rec)
            stats["matched"] += 1
        except Exception as exc:
            logger.warning("LLM matching failed for %s: %s", name, exc)
            stats["failed"] += 1

        output_data = {
            "school": data.get("school"),
            "college": data.get("college"),
            "recommendations": recommendations,
            "stats": stats,
        }
        Path(output_path).write_text(
            json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if i < len(profiles) - 1:
            time.sleep(delay)

    logger.info("Matching complete: %s", stats)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-powered teacher matching")
    parser.add_argument("--input", required=True, help="Input llm_enriched.json path")
    parser.add_argument("--resume", required=True, help="User resume text file")
    parser.add_argument("--interests", required=True, help="User research interests text file")
    parser.add_argument("--output", required=True, help="Output recommendations.json path")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between API calls")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)
    stats = run_matching(args.input, args.resume, args.interests, args.output, delay=args.delay)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/kalin/github/baoyan_search_teachar && python -m pytest tests/test_match_engine.py -v`
Expected: 2 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/llm/match_engine.py tests/test_match_engine.py
git commit -m "feat: add LLM match engine for teacher recommendation"
```

---

### Task 6: Run all tests and final validation

**Files:** None (validation only)

- [ ] **Step 1: Run all LLM-related tests**

Run: `cd /Users/kalin/github/baoyan_search_teachar && python -m pytest tests/test_llm_client.py tests/test_profile_extractor.py tests/test_match_engine.py -v`
Expected: all tests pass

- [ ] **Step 2: Run existing tests to check no regression**

Run: `cd /Users/kalin/github/baoyan_search_teachar && python -m pytest tests/ -v`
Expected: all existing tests still pass

- [ ] **Step 3: Verify CLI help works**

Run: `cd /Users/kalin/github/baoyan_search_teachar && python src/llm/profile_extractor.py --help`
Expected: shows argparse help text

Run: `cd /Users/kalin/github/baoyan_search_teachar && python src/llm/match_engine.py --help`
Expected: shows argparse help text
