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
  "research_keywords": ["2-8个研究方向关键词"],
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
6. recruiting_targets 从 ["phd", "master", "postdoc", "intern", "ra"] 中选零个、一个或者多个

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

重要：如果教师信息完全为空（没有研究方向、个人简介等任何有效信息），则无法做出可靠判断，match_score 应为 0 并在 risk_flags 中标记"info_missing"。但只要教师有有效信息（比如有研究方向关键词或一段简短的个人简介），就应该根据已有信息尽力评估匹配度，不要因为没有完整信息就放弃判断。信息不足时，可以在 risk_flags 中标记"info_limited"并适当降低分数，但不要直接给 0 分。

输出 JSON：
{
  "match_score": 85,
  "match_reasons": ["匹配理由1", "匹配理由2"],
  "risk_flags": ["风险因素1"]
}

只输出 JSON，不要输出其他内容。"""
