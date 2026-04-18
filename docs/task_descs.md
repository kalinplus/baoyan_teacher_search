## 总体描述
目标是做一个可批量运行的 CLI 工具（初期脚本即可）。
输入是学校+学院教师池（批量）或学校+姓名（单人），输出包括三层信息：
- 基本信息（主页/邮箱/实验室/招生信号等）
- 学术结构化信息（Google Scholar）
- 推荐程度（综合排序）

核心原则：先用低成本信息做预筛，再用付费 API 做精筛，控制配额消耗。

## 推荐执行链路（重新整理）
1. 任务0：获取教师池（名单）
2. 任务1：获取基本信息并预筛（新增前置核心阶段）
3. 任务2：获取 Google Scholar 结构化信息（仅对预筛后的候选）
4. 任务3：匹配度分析与推荐排序
5. 任务4：CLI / GUI 封装

## 任务0：获取教师列表（Teacher Pool）
- 输入：学校+学院+教师列表 URL（本地维护数据文件）
- 处理：抓取整页 HTML，自动识别教师条目并提取基础字段（姓名、教师主页 URL、邮箱、研究兴趣、职称），再清洗去重
- 输出：按学院落盘教师池，供后续任务消费（兼容旧字段 + 新增结构化资料）

当前现状：
- 已落地 `teachers + teacher_profiles` 双轨输出（向后兼容），`teacher_profiles` 包含 `name/profile_url/email/interests/title/source_url`。
- 清华与上海交通大学重点学院已打通，SJTU 计算机学院主入口采用 AJAX 名录解析，空结果回退 CSE 旧页。
- 执行策略已稳定为“自动识别优先，站点规则兜底”，并通过回归测试保障字段契约。

任务0输出契约（已落地）：
- 保留现有 teachers（纯姓名列表），保证向后兼容
- 新增 teacher_profiles（结构化列表），每项至少包含：
	- name
	- profile_url（若页面无详情页则为 null）
	- email（若页面可提取则为邮箱，否则为 null）
	- interests（列表页可提取的研究方向关键词数组）
	- title（教授/副教授/助理教授等，无法识别时为 null）
	- source_url（该老师被发现的列表页）

## 任务1：获取基本信息并预筛（前置于结构化信息）
这是新的关键阶段，目标是减少后续 API 请求规模。

### 1. 输入
- 任务0输出的教师池（学校/学院/姓名/列表页URL）
- 已联系老师名单（命中即硬跳过）
- 可选：学院优先级、个人方向关键词

### 2. 处理
- 从列表页或教师主页提取基础信号：
	- 主页链接是否可用
	- 邮箱是否公开
	- 职称/岗位关键词（教授/副教授/研究员等）
	- 招生相关关键词（招生、招收、prospective students 等）
	- 近期活跃信号（近年新闻/论文/项目）
	- 研究方向关键词匹配度
- 生成预筛分数与原因标签
- 输出候选优先级列表（Top N 进入任务2）

### 3. 输出
- 预筛结果（包含分数、特征、排序理由、是否跳过）
- 跳过原因（已联系/信息不足/超出预算）

备注：
- 该阶段优先用学校站点公开页面完成，通常无 API 成本或低成本。
- 这一步不是替代 Scholar，而是为 Scholar 调用“控量+提质”。
- 优先使用任务0已抽取的 teacher_profiles 字段，减少重复页面请求。

## 任务2：获取 Google Scholar 结构化信息（精筛阶段）
仅对任务1输出的候选老师执行，避免全量调用。

### 当前实现（已具备）
- 基于学校+姓名自动解析 author_id：src/author_id_resolver.py
- 基于 author_id 获取结构化信息：src/scholar_client.py
- 已实现 author_id 本地缓存（避免重复搜索）
- 支持 DEBUG 日志追踪解析链路
- 查询策略：单次查询 `site:scholar.google.com/citations + 学校英文缩写 + 老师检索词`
- 中文姓名检索词已通过 pypinyin 转写（含复姓配置）

### result.json 关键字段（当前契约）
- author_id
- name
- affiliations
- email
- interests
- citations_all
- citations_last_1y
- citations_last_3y
- citations_last_5y
- publications_total
- publications_last_1y
- publications_last_3y
- publications_last_5y
- publications_truncated
- h_index_all
- i10_index_all
- source
- matched_school
- matched_teacher

参考 API 文档：

ScraperAPI：
- 通用代理端点（用于抓 Google Search）：<https://docs.scraperapi.com/synchronous-apis/using-the-api-endpoint>
- Google Search 结构化端点（参考）：<https://docs.scraperapi.com/structured-data-endpoints/search-and-insights/google/google-serp-api>
- 结构化端点总览：<https://docs.scraperapi.com/structured-data-endpoints>

SerpApi：
- Google Scholar 主文档：<https://serpapi.com/google-scholar-api>
- Google Scholar Author 引擎：<https://serpapi.com/google-scholar-author-api>

## 任务3：匹配度分析与推荐排序
分两层：
1. 规则层：用兴趣关键词、研究方向、院校/学院偏好、学术指标做初步打分
2. LLM 层：输入简历（md）与老师画像，输出解释型匹配建议

建议将任务1和任务2的特征统一到一个评分输入，避免重复排序逻辑。

## 任务4：CLI 甚至 GUI 包装
- CLI 先行，保障可批处理与可复跑
- GUI 作为后续增强，不影响主链路

## 当前优先 TODO（按执行顺序）
1. 任务1优先：基于老师主页与列表页信号建立预筛特征表（可达性、职称、招生关键词、方向匹配、活跃度）。
2. 任务2控量：仅对任务1的 Top N 候选执行 Google Scholar 结构化抓取，减少配额消耗。
3. 融合输出：在老师维度合并“主页信号 + Scholar 指标”，形成可直接使用的信息参考卡。
4. 推荐排序：输出可解释推荐结果（分数、证据来源 URL、关键指标摘要、风险提示）。
5. 工程化收口：补充“已联系名单硬跳过 + 预算上限 + 结果复核清单”，支持稳定批处理。