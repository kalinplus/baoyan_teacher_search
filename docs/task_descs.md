## 总体描述
目标是做一个可批量运行的 CLI 工具。输入是学校+学院教师池（批量）或学校+姓名（单人），输出包括三层信息：基本信息、学术结构化信息（Google Scholar）、推荐程度。

核心原则：先用低成本信息做预筛，再用付费 API 做精筛，控制配额消耗。

## 推荐执行链路

1. 任务0：获取教师池（名单）
2. 任务1：获取基本信息并预筛
3. 任务2：获取 Google Scholar 结构化信息（仅对预筛后的候选）
4. 任务3：匹配度分析与推荐排序
5. 任务4：CLI / GUI 封装

## 各任务状态

### 任务0：获取教师列表（Teacher Pool）
- **状态**：已完成
- **说明**：已实现 `teachers + teacher_profiles` 双轨输出，清华 8 个院系 + 上海交大 4 个院系 + 浙大 2 个院系 + 上海创智学院 1 个院系已适配，策略为”自动识别优先，站点规则兜底”。
- **字段契约**：见 `README.md`「任务0 Step2」章节。

### 任务1：获取基本信息并预筛 + 批量闭环
- **状态**：已完成
- **说明**：硬过滤 + 加权评分 + A/B/C 分层 + `top_n/budget` 裁剪已落地。批量闭环（`prescreen -> author_id -> scholar -> recommendation`）已串联，输出 `final_recommendations.json`。
- **字段契约**：见 `README.md`「离线预筛」与「任务1批量闭环」章节。

### 任务2：获取 Google Scholar 结构化信息
- **状态**：已完成
- **说明**：`author_id_resolver.py` 自动发现 + `scholar_client.py` 结构化抓取已落地。author_id 首候选执行两层校验（缓存反查冲突 + Scholar 主页姓名一致性），中文姓名通过 `pypinyin` 转写。
- **字段契约**：见 `README.md`「result.json 关键字段」章节。

### 任务3：匹配度分析与推荐排序
- **状态**：已完成
- **说明**：LLM Pipeline（`src/llm/pipeline.py`）已落地，基于 SiliconFlow DeepSeek-V3 实现教师信息提取与匹配推荐，输出 `match_score/match_reasons/risk_flags`。已产出 5 个学院的 `recommendations.json`。
- **字段契约**：见 `README.md`「LLM Pipeline」章节。

### 任务4：CLI / GUI 封装
- **状态**：已完成（CLI）
- **说明**：CLI 已覆盖全部链路；新增 `recommendations_to_html.py` 将推荐结果转为可搜索/排序的 HTML 报告，浏览器直接查看。GUI 作为后续增强。

## 当前优先 TODO

1. LLM 提取质量评估：抽样校验 `llm_basic` / `llm_extended` 字段准确率，优化 prompt。
2. 推荐结果优化：分析 5 个学院 recommendations.json，调整匹配 prompt 减少误匹配。
3. 工程化收口：补充“预算上限 + 已联系名单 + skip 原因统计”的端到端回归验证。

## 历史执行记录

- 2026-04-24：新增上海创智学院（SII）教师页适配，通过 AJAX API 全量采集 73 位导师（全职/全时/分时）。
- 2026-04-22：新增 `recommendations_to_html.py`，将 `recommendations.json` 批量转为可搜索/排序的 HTML 报告。
- 2026-04-21：LLM Pipeline 落地（`src/llm/llm_client.py`、`prompts.py`、`profile_extractor.py`、`match_engine.py`、`pipeline.py`），接入 SiliconFlow DeepSeek-V3 API，产出 5 个学院 recommendations.json。
- 2026-04-19：批量闭环模块（`batch_closed_loop.py`、`author_disambiguation.py`、`scholar_batch_runner.py`、`recommendation_assembler.py`）落地，补齐单测与文档同步。
- 2026-04-19：author_id 首候选两层校验（缓存反查冲突 + Scholar 主页姓名一致性）落地。
- 2026-04-19：批量抓取容错（老师级 continue）与网络重试（2 次重试 + 递增超时）落地并通过单测。
- 2026-04-19：离线预筛（硬过滤 + 评分 + A/B/C 分层 + `top_n/budget` 裁剪）落地，配置外置到 `config/prescreen_scoring.json`。
- 2026-04-18：上海交大 4 个院系教师页适配完成，SJTU 计算机学院主入口支持 AJAX 名录解析。
- 2026-04-17：清华大学 8 个院系教师页适配完成，SIGS 学科白名单外置到 `config/sigs_subject_keywords.json`。
- 2026-04-17：浙江大学计算机学院、软件学院教师页适配完成。
