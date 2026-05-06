## 总体描述
目标是做一个可批量运行的 CLI 工具。输入是学校+学院教师池（批量），输出为按匹配度排序的导师推荐报告（JSON + HTML）。

~~核心原则：先用低成本信息做预筛，再用付费 API 做精筛，控制配额消耗。~~（已调整：预筛已废弃，全部候选直接走 LLM Pipeline。）

## 推荐执行链路

1. 任务0：获取教师池（名单）
2. ~~任务1：获取基本信息并预筛~~（已废弃）
3. 任务0.5：教师主页详情抓取（补充 homepage 字段）
4. ~~任务2：获取 Google Scholar 结构化信息~~（已废弃）
5. 任务3：LLM 提取教师信息 + 匹配度分析与推荐排序
6. 任务4：CLI / GUI 封装

## 各任务状态

### 任务0：获取教师列表（Teacher Pool）
- **状态**：已完成
- **说明**：已实现 `teachers + teacher_profiles` 双轨输出，清华 8 个院系 + 上海交大 4 个院系 + 浙大 2 个院系 + 上海创智学院 1 个院系 + 复旦 1 个院系已适配，策略为”自动识别优先，站点规则兜底”。
- **字段契约**：见 `README.md`「任务0 Step2」章节。

### ~~任务1：获取基本信息并预筛 + 批量闭环~~（已废弃）
- **状态**：已废弃
- **说明**：~~硬过滤 + 加权评分 + A/B/C 分层 + `top_n/budget` 裁剪已落地。批量闭环（`prescreen -> author_id -> scholar -> recommendation`）已串联，输出 `final_recommendations.json`。~~
- **废弃原因**：规则预筛已由 LLM Pipeline 替代。全部候选（含 homepage 结构化字段）直接输入 LLM 做提取与匹配，不再做 A/B/C 分层和 budget 裁剪。

### ~~任务2：获取 Google Scholar 结构化信息~~（已废弃）
- **状态**：已废弃
- **说明**：~~`author_id_resolver.py` 自动发现 + `scholar_client.py` 结构化抓取已落地。author_id 首候选执行两层校验（缓存反查冲突 + Scholar 主页姓名一致性），中文姓名通过 `pypinyin` 转写。~~
- **废弃原因**：LLM Pipeline（任务3b）已替代 Scholar 链路作为核心推荐引擎，author_id 解析与 SerpApi 抓取不再维护，相关代码保留但不做迭代。

### 任务3：匹配度分析与推荐排序（LLM 版）
- **状态**：已完成（LLM 版）；规则版已废弃
- **说明**：LLM Pipeline（`src/llm/pipeline.py`）已落地，基于 SiliconFlow DeepSeek-V3 实现教师信息提取与匹配推荐，输出 `match_score/match_reasons/risk_flags`。已产出 5 个学院的 `recommendations.json`。
- **废弃说明**：原规则版推荐（`recommendation_assembler.py`，基于 Scholar 指标拼接推荐理由）随 Scholar 链路一同废弃。
- **字段契约**：见 `README.md`「LLM Pipeline」章节。

### 任务4：CLI / GUI 封装
- **状态**：已完成（CLI）
- **说明**：CLI 已覆盖全部链路；新增 `recommendations_to_html.py` 将推荐结果转为可搜索/排序的 HTML 报告，浏览器直接查看。GUI 作为后续增强。
- **状态标记（已发送）**：HTML 报告支持逐卡勾选"已发送"，勾选后卡片添加删除线并降低透明度，状态通过 `localStorage` 按 `school·college` 维度持久化，刷新不丢失。

## 当前优先 TODO

1. LLM 提取质量评估：抽样校验 `llm_basic` / `llm_extended` 字段准确率，优化 prompt。
2. 推荐结果优化：分析 5 个学院 recommendations.json，调整匹配 prompt 减少误匹配。
3. 工程化收口：补充“预算上限 + 已联系名单 + skip 原因统计”的端到端回归验证。

## 待办学院适配（任务0 扩展）

- [x] 中国科学院自动化研究所（自动化所）教师页适配
- [x] 中国科学院计算技术研究所（计算所）教师页适配
- [ ] 中国科学院软件研究所（软件所）教师页适配
- [x] 中国人民大学高瓴人工智能学院（人大高瓴）教师页适配
- [x] 南京大学计算机相关学院教师页适配（计算机科学与技术系、人工智能学院、软件学院等）

## 历史执行记录

- 2026-05-06：新增中国科学院计算技术研究所（计算所）博士生导师 + 硕士生导师页适配，通过 `sourcedb/cn/jssrck` 个人主页链接提取 213 位导师（博导 103 + 硕导 110，去重），profile scraper 结构化解析 `p-people-content` + `tem01-people-content` 分节提取，成功率 ~90%，LLM Pipeline 匹配 28/213。
- 2026-05-05：新增中国科学院自动化研究所（自动化所）研究生导师页适配，通过表格内 `people.ucas.(ac|edu).cn` 链接提取 222 位导师，profile scraper 成功率 99.1%，LLM Pipeline 匹配 219/222。
- 2026-04-25：新增复旦大学计算与智能创新学院教师页适配，通过 `_wp3services/generalQuery?queryObj=teacherHome` API 全量采集 287 位教职工。
- 2026-04-24：新增上海创智学院（SII）教师页适配，通过 AJAX API 全量采集 73 位导师（全职/全时/分时）。
- 2026-04-22：新增 `recommendations_to_html.py`，将 `recommendations.json` 批量转为可搜索/排序的 HTML 报告。
- 2026-04-21：LLM Pipeline 落地（`src/llm/llm_client.py`、`prompts.py`、`profile_extractor.py`、`match_engine.py`、`pipeline.py`），接入 SiliconFlow DeepSeek-V3 API，产出 5 个学院 recommendations.json。
- 2026-04-19：批量闭环模块（`batch_closed_loop.py`、`author_disambiguation.py`、`scholar_batch_runner.py`、`recommendation_assembler.py`）落地，补齐单测与文档同步。
- 2026-04-19：author_id 首候选两层校验（缓存反查冲突 + Scholar 主页姓名一致性）落地。
- 2026-04-19：批量抓取容错（老师级 continue）与网络重试（2 次重试 + 递增超时）落地并通过单测。
- 2026-04-19：离线预筛（硬过滤 + 评分 + A/B/C 分层 + `top_n/budget` 裁剪）落地，配置外置到 `config/prescreen_scoring.json`。
- 2026-04-18：上海交大 4 个院系教师页适配完成，SJTU 计算机学院主入口支持 AJAX 名录解析。
- 2026-04-26：清华计算机科学与技术系教师个人主页（`info/*.htm`）增加结构化解析路径，提取 `v_news_content` 内固定字段与分节内容，解决通用文本清洗导致的 `full_text` 导航噪音问题（从 103 行压缩到 ~20 行）；同时为 `thu.py` 补全 `profile_extractor`，修正此前 `profile_url` 全部为导航链接的严重数据质量问题（127 位真实教师，0 失败）。
- 2026-04-26：上交计算机学院教师个人主页（`jiaoshiml/*.html`）增加结构化解析路径，解决通用文本清洗导致的 email 污染、title 精度丢失、bio 截断问题，为 LLM 提取生成更高质量的 `full_text`。
- 2026-04-17：清华大学 8 个院系教师页适配完成，SIGS 学科白名单外置到 `config/sigs_subject_keywords.json`。
- 2026-04-17：浙江大学计算机学院、软件学院教师页适配完成。
