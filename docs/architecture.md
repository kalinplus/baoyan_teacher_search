# 项目架构文档

## 一、项目概述

保研导师信息抓取与推荐系统。输入学校+学院，输出导师推荐列表（含学术指标、研究方向、推荐理由）。

核心思路：**分层漏斗**，先用免费信息做预筛，再用付费 API 做精筛，控制成本。

## 二、技术栈

- **语言**：Python 3.9
- **HTTP**：requests（页面抓取）
- **付费 API**：SerpApi（Google Scholar 结构化查询）、ScraperApi（author_id 自动发现时的 Google 搜索代理）
- **数据处理**：正则 + html.unescape（无 BeautifulSoup 依赖）
- **拼音**：pypinyin（中文姓名→拼音，用于 Google Scholar 搜索）
- **测试**：unittest
- **配置**：JSON 文件（评分权重、学科白名单、已联系名单等）

## 三、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    任务0: 教师池抓取                         │
│                                                             │
│  source_urls.json ──→ teacher_list_collector ──→ teachers.json│
│                          │                                   │
│                    ┌─────┴──────┐                            │
│                    │ auto 提取  │ 通用逻辑                    │
│                    │ + rule 兜底 │ 学校规则(可选)             │
│                    └────────────┘                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│               任务0.5: 教师主页详情抓取                      │
│                                                             │
│  teachers.json ──→ teacher_profile_scraper ──→ teachers.json │
│                                                             │
│  对每个 profile_url 抓取学院详情页，提取研究方向、个人简介、 │
│  邮箱、职称、代表工作、外部主页、招生信息，写回 homepage 字段│
│  并回填 email/title。文本清洗: 去 script/style → 去重 nav   │
│  → nav关键词过滤 → 短行块过滤。并发3，间隔0.3s。           │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    任务1: 离线预筛                           │
│                                                             │
│  teachers.json + contacted_teachers.json + scoring.json      │
│       ──→ teacher_list_prescreen ──→ prescreen.json         │
│                                                             │
│  入口: collector --prescreen-dir (读磁盘，不重新采集)        │
│  逻辑: 硬过滤(已联系/负面信号) → 加权评分(含 homepage 关键词│
│       匹配) → A/B/C分层 → top_n 裁剪                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ top_candidates (通常 20 人)
┌──────────────────────────▼──────────────────────────────────┐
│                  任务2: Scholar 抓取                         │
│                                                             │
│  prescreen.json                                            │
│    → author_id_resolver (自动发现 author_id)                │
│    → scholar_client (抓取学术指标)                           │
│                                                             │
│  环境: SERPAPI_KEY + SCRAPERAPI_KEY                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  任务3: 推荐组装（规则版）                   │
│                                                             │
│  prescreen + scholar metrics                                │
│    → recommendation_assembler ──→ final_recommendations.json│
│                                                             │
│  输出: 推荐理由 + 风险标记 + 失败明细                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                  任务3b: LLM 匹配推荐（新版）                │
│                                                             │
│  teachers.json (with full_text)                             │
│    → profile_extractor ──→ llm_enriched.json                │
│    → match_engine ──→ recommendations.json                  │
│                                                             │
│  输入: 简历 + 研究兴趣; 输出: match_score + match_reasons   │
└─────────────────────────────────────────────────────────────┘
```

## 四、模块职责

### 4.1 教师池抓取（任务0）

| 文件 | 职责 |
|------|------|
| `teacher_list_collector.py` | CLI 入口，调度抓取流程；`--prescreen-dir` 模式从磁盘读取做预筛 |
| `teacher_list_core.py` | 通用提取引擎：自动提取 + 规则兜底 + 质量比较 |
| `teacher_list_models.py` | 数据模型：`TeacherProfile`、`SourceRecord`、`Rule` |
| `teacher_list_helpers.py` | 文本工具：姓名识别、噪音过滤、URL 解析、兴趣提取 |
| `teacher_list_io.py` | 输入读取、JSON/JSONL 导出 |
| `teacher_list_prescreen.py` | 离线预筛引擎（硬过滤 + 评分 + homepage关键词匹配 + 分层） |
| `teacher_profile_scraper.py` | 教师详情页抓取：提取研究方向/bio/email/title/代表工作/个人主页 |
| `teacher_extractors/` | **学校特定规则**，每个学校一个 `.py` |

### 4.2 Scholar 抓取 + 推荐（任务2/3）

| 文件 | 职责 |
|------|------|
| `scholar/scholar_client.py` | 通过 SerpApi 抓取 Google Scholar 学者主页（引用、发文、h-index 等） |
| `scholar/author_id_resolver.py` | 自动发现 author_id：中文姓名→拼音→Google 搜索→正则提取→两层校验 |
| `scholar/author_disambiguation.py` | author_id 解析的错误处理和 skip_reason 记录 |
| `scholar/scholar_batch_runner.py` | 批量调用 Scholar 抓取 |
| `batch_closed_loop.py` | 批量闭环编排：串联预筛→author_id→scholar→推荐，老师级容错 |
| `recommendation_assembler.py` | 组装推荐理由和风险标记 |

### 4.3 LLM Pipeline（任务3b）

| 文件 | 职责 |
|------|------|
| `llm/llm_client.py` | SiliconFlow OpenAI-compatible API 封装，含重试与 JSON 解析 |
| `llm/prompts.py` | 提取与匹配的 prompt 模板 |
| `llm/profile_extractor.py` | Step3：从 `full_text` 批量提取结构化教师信息（basic + extended） |
| `llm/match_engine.py` | Step4：基于简历/兴趣与教师信息做 LLM 匹配评分 |
| `llm/pipeline.py` | 端到端编排：extraction → matching |

### 4.3 辅助

| 文件 | 职责 |
|------|------|
| `utils.py` | 日志配置 |

## 五、学校适配机制

### 5.1 设计思路

**通用逻辑 + 规则兜底**，不是每所学校都必须写规则：

1. 先用 `extract_teacher_profiles_auto()` 做通用自动提取（基于 `<a>` 标签模式匹配）
2. 如果 URL 匹配到某个学校规则，用规则提取的结果与自动提取比较
3. 规则结果更丰富（更多 profile_url、email 等）时，优先使用规则结果

### 5.2 适配接口

每个学校文件实现 `get_rules()` 返回规则列表：

```python
Rule(
    name="pku_cs_h3big",          # 规则名称
    matcher=supports_pku_cs,       # URL 匹配函数
    extractor=extract_pku_cs_names,        # 简单姓名列表（可选）
    profile_extractor=extract_pku_cs_profiles,  # 富字段提取（可选）
)
```

- `matcher(url) -> bool`：判断 URL 是否匹配此规则
- `extractor(html) -> List[str]`：提取姓名列表
- `profile_extractor(html, source_url) -> List[TeacherProfile]`：提取完整 profile

### 5.3 已适配学校

| 学校 | 文件 | 已适配学院数 |
|------|------|-------------|
| 清华 | `teacher_extractors/thu.py` | 8（计算机、软件、AI、交叉信息、网络、自动化、电子工程、深研院） |
| 上交 | `teacher_extractors/sjtu.py` | 5（AI学院全职/双聘、计算机、浦江、溥渊） |
| 北大 | `teacher_extractors/pku.py` | 2（计算机学院、人工智能研究院） |
| 浙大 | `teacher_extractors/zju.py` | 2（计算机学院、软件学院） |

### 5.4 新增学校步骤

1. 分析目标学院教师页 HTML 结构
2. 在 `teacher_extractors/` 下新建 `{school}.py`
3. 实现 `get_rules()` + 对应的 matcher/extractor 函数
4. 在 `teacher_extractors/__init__.py` 注册
5. 在 `docs/task0/source_urls.json` 添加 URL
6. 在 `config/universities.json` 确认学校名映射存在
7. 运行 + 验证

**无规则学校**：通用自动提取会兜底，但可能包含噪音、缺少 profile_url 等字段。

## 六、配置文件

| 文件 | 用途 |
|------|------|
| `config/universities.json` | 52 所高校名称别名映射（输入归一化） |
| `config/compound_surnames.json` | 31 个复姓（拼音转换用） |
| `config/sigs_subject_keywords.json` | 清华深研院学科白名单 |
| `config/contacted_teachers.json` | 已联系教师名单（预筛硬过滤） |
| `config/prescreen_scoring.json` | 预筛评分权重和分层阈值 |
| `docs/task0/source_urls.json` | 抓取目标 URL 列表（学校/学院/URL） |

## 七、数据契约

### 7.1 教师池输出 (`teachers.json`)

```json
{
  "school": "北京大学",
  "college": "计算机学院",
  "url": "https://cs.pku.edu.cn/szdw/jyxl/amz/ALL.htm",
  "teachers": ["边凯归", "曹东刚", "..."],
  "teacher_profiles": [
    {
      "name": "边凯归",
      "profile_url": "https://cs.pku.edu.cn/info/1061/1602.htm",
      "email": null,
      "interests": ["计算机网络"],
      "title": "长聘副教授",
      "source_url": "https://cs.pku.edu.cn/szdw/jyxl/amz/ALL.htm",
      "homepage": {
        "full_text": "清洗后的完整文本...",
        "research_fields": ["无线网络", "移动计算"],
        "bio": "个人简介文本",
        "email": null,
        "title": "长聘副教授",
        "representative_works": "代表性论著文本",
        "personal_homepage": "https://example.com",
        "recruiting_status": "unknown",
        "conferences": ["MobiCom", "INFOCOM"]
      }
    }
  ]
}
```

### 7.2 最终推荐输出 (`final_recommendations.json`)

```json
{
  "school": "...",
  "college": "...",
  "generated_at": "2026-04-20T10:30:00",
  "total_candidates": 20,
  "resolved_candidates": 18,
  "failed_candidates": 2,
  "recommendations": [
    {
      "teacher": "张三",
      "prescreen_score": 85,
      "prescreen_tier": "A",
      "author_id": "xxx",
      "scholar_metrics": {
        "citations_all": 2341,
        "h_index_all": 18,
        "publications_last_3y": 15
      },
      "recommendation_reason": "tier=A; score=85; citations=2341; pub_3y=15",
      "risk_flags": []
    }
  ]
}
```

## 八、关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| HTML 解析 | 正则，无 BeautifulSoup | 减少依赖，页面结构简单够用 |
| 自动提取 vs 规则 | 自动优先，规则兜底 | 无规则学校也能用，规则提供更精确结果 |
| 作者发现 | Google 搜索 + 缓存 + 两层校验 | 自动化，但需要付费代理 |
| 预筛策略 | 配置驱动评分 | 调参不改代码 |
| 批量容错 | 老师级 continue | 单失败不阻塞整批 |
| 分页抓取 | 在 extractor 内部发请求 | 对调用方透明 |
| 预筛与采集解耦 | `--prescreen-dir` 读磁盘 | 避免重新采集覆盖 scraper 写入的 homepage 数据 |
| 详情页文本清洗 | 去 script → 标签转文本 → 去重 → nav关键词 → 短行块 | 各校 HTML 结构差异大，无法用结构选择器统一处理 |
| Nav 过滤核心策略 | 去重（出现≥2次的行视为 nav） | 各校菜单均为移动端+桌面端双份，去重最通用有效 |

## 九、已知限制

1. **同名消歧**：author_id 自动发现仅取首个候选，同名时可能匹配错误
2. **JS 渲染页面**：清华电子工程系(147人)用 JS 注入数据，无 profile_url，无法抓取详情
3. **图片邮箱**：北大 CS 用图片拆分 `@` 符号，email 提取率仅 1%；上交 99%、清华 58%
4. **推荐规则**：规则版（recommendation_assembler）仅简单拼接；LLM 版（match_engine）已落地，但 prompt 质量仍在迭代中
5. **增量更新**：无，每次全量抓取
6. **Nav 噪音**：去重策略对双份菜单有效，但仅出现一次的导航项仍会残留少量
7. **LLM 成本**：~1500 教师 × ~5k tokens ≈ 15M input tokens，每次全量运行需消耗 API 配额

## 十、目录结构

```
├── src/
│   ├── scholar/
│   │   ├── scholar_client.py           # Scholar 抓取核心
│   │   ├── author_id_resolver.py       # author_id 自动发现
│   │   ├── author_disambiguation.py    # author_id 错误处理
│   │   └── scholar_batch_runner.py     # Scholar 批量执行
│   ├── llm/
│   │   ├── llm_client.py               # SiliconFlow API 封装
│   │   ├── prompts.py                  # Prompt 模板
│   │   ├── profile_extractor.py        # LLM 教师信息提取
│   │   ├── match_engine.py             # LLM 匹配推荐
│   │   └── pipeline.py                 # 端到端 LLM 流水线
│   ├── teacher_list_collector.py       # 任务0 入口（含 --prescreen-dir 模式）
│   ├── teacher_list_core.py            # 通用提取引擎
│   ├── teacher_list_models.py          # 数据模型
│   ├── teacher_list_helpers.py         # 文本工具
│   ├── teacher_list_io.py              # IO 导出
│   ├── teacher_list_prescreen.py       # 离线预筛（含 homepage 关键词匹配）
│   ├── teacher_profile_scraper.py      # 教师详情页抓取（任务0.5）
│   ├── teacher_extractors/             # 学校特定规则
│   │   ├── __init__.py                 # 规则注册
│   │   ├── thu.py                      # 清华 (8 学院)
│   │   ├── sjtu.py                     # 上交 (5 学院)
│   │   ├── pku.py                      # 北大 (2 学院)
│   │   └── zju.py                      # 浙大 (2 学院)
│   ├── batch_closed_loop.py            # 批量闭环编排
│   ├── recommendation_assembler.py     # 推荐组装
│   └── utils.py                        # 日志
├── config/                             # 配置文件
├── docs/                               # 文档
├── tests/                              # 单测
├── output/                             # 输出目录
├── html_report/                        # HTML 推荐报告（由 recommendations_to_html.py 生成）
├── recommendations_to_html.py          # recommendations.json → HTML 转换脚本
├── requirements.txt
└── AGENT.md / CLAUDE.md                # AI 协作指令
```
