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
