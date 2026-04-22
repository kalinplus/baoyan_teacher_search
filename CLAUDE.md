# CLAUDE.md

本文件是本仓库的统一代理入口说明（类似 CLAUDE.md）。

## Project Guidelines

### Code Style
- 使用 Python 进行实现，保持函数和类命名清晰、职责单一。
- 变更时优先保持输出字段契约稳定，避免随意增删 result.json 字段。
- 仅在必要时添加注释，注释应解释业务意图而不是逐行复述代码。

### Architecture
- 当前唯一运行入口是 src/scholar/scholar_client.py。
- 通过 ScholarAuthorClient 类调用 SerpApi，主方法是 query_structured_info(author_id)。
- 学校归一化配置来自 config/universities.json。
- 输出目录结构固定为 output/{学校全称}/{老师姓名}/，包含 result.json 和 summary.md。

### Build and Test
- 安装依赖: pip install -r requirements.txt
- 运行命令: python src/scholar/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output
- 快速验收: python -c "import json,pathlib;p=pathlib.Path('output/清华大学/夏树涛/result.json');d=json.loads(p.read_text(encoding='utf-8'));print(d.get('name'))"
- 当前仓库未配置单元测试框架；改动后至少执行一次运行命令和一次输出校验。

### Conventions
- 必须提供环境变量 SERPAPI_KEY，否则程序会抛出运行时错误。
- school 参数必须能在 config/universities.json 中归一化，否则会抛出 ValueError。
- 默认支持学校+老师自动发现 author_id；也允许显式传入 author_id。
- 自动发现依赖 SCRAPERAPI_KEY。
- source 字段应包含 author_id 来源与 scholar_author（例如 google_search,scholar_author）。

### Personal Engineering Preferences
1. Fail fast and loudly: Do not write fallback logic unless it is explicitly required.
2. Let exceptions/errors bubble up early: Do not handle errors inside business layers.
3. Valid test principle: Prove a bug/problem exists by making it fail first. Tests that only pass prove little.

### Docs
- 项目运行与字段契约: README.md
- 阶段任务描述: docs/task_descs.md
- 阶段2进度: docs/stage2/progress.md
- Step1契约: docs/task1/step1_contract.md
- 批量闭环后续计划: docs/task1/batch_closed_loop_plan.md
- 问题归档: docs/archive/stage2_issues.md
- 技术路线背景: docs/google_scholar_info.md

## Approval And Safety Rules

1. 新增依赖需先审批
- 任何新增依赖（包括 requirements、锁文件或等效依赖配置）在落盘前必须先获得确认。

2. 允许自动执行 CI/脚本相关命令
- 允许自动运行构建、测试、校验、脚本执行等命令，不要求逐条审批。

3. 命令执行范围
- 只读、测试、构建、脚本命令均可自动执行。

4. 高风险操作默认禁止
- 默认禁止高风险操作，除非获得明确授权。
- 高风险操作包括但不限于：破坏性删除、大范围覆盖、不可逆回滚、强制历史改写、生产环境写操作。

5. 默认不改全局配置
- 默认不修改系统级或用户级全局配置（如全局 git 配置、shell 配置、IDE 全局配置）。
- 若确有必要，需先说明影响范围并获得审批。

6. 文档同步规则
- 影响行为、参数、输出契约时，必须同步更新 README 与任务卡。
- 文档与代码不一致时，标记为阻塞项，先完成对齐再继续后续工作。
- 文档被告知重命名，或发现文档已重命名时，必须同步更新其他关联文档中的引用与说明。

## Session Progress

<!-- 每次 session 结束前由 copilot 更新，格式：[时间] [这次做了什么] [下次待做什么] -->
- [2026-04-14] [完成学校+老师自动发现 author id，并根据 author id 获取 Google Scholar 主页信息并爬取到本地] [补充自动发现流程的回归验证与文档对齐]
- [2026-04-16] [将 session 进展记录规范追加到 AGENT.md 末尾，并落地首批进展条目] [后续每次 session 结束前按统一格式持续更新本区块]
- [2026-04-16] [完成任务0 Step2“规则驱动+站点适配器”方案文档与实施里程碑，明确无需外部API即可先推进] [按学院页面结构逐条实现提取规则并做抽样验收]
- [2026-04-17] [实现任务0抓取入口并完成清华大学计算机科学与技术系规则适配，修复 requests 默认编码导致中文名单提取为空的问题，产出127位教师名单] [按 thu_teachar_page.md 继续扩展软件学院/人工智能学院等学院规则并补充抽样验收]
- [2026-04-17] [按分层设计重构 teacher_list_collector：通用抓取/清洗/验证迁移至核心模块，站点提取规则迁移至 teacher_extractors 子目录，保持 CLI 与输出行为不变] [在 teacher_extractors 下继续新增更多学院规则并补充分页与二级页支持]
- [2026-04-17] [新增清华软件学院、人工智能学院（仅全职PI）、交叉信息研究院（全职教师+研究系列）规则并完成实抓，分别产出41/13/47名教师且通过非空去重导航词校验] [继续扩展网络科学与网络空间研究院、自动化系等页面规则]
- [2026-04-17] [新增清华网络科学与网络空间研究院、自动化系规则并完成实抓，产出54/59名教师，均通过非空去重与噪音词抽样校验] [继续扩展电子工程系（中文页优先）与深圳国际研究生院规则并评估英文名转换策略]
- [2026-04-17] [完成电子工程系中文在职教师页与深圳国际研究生院新链接（7644/list）规则适配并实抓，产出147/14名教师；SIGS结果包含夏树涛、郑海涛、吴志勇、江勇、袁春] [后续可针对SIGS“计算机方向”过滤策略补充可配置关键词与人工复核门禁]
- [2026-04-17] [将SIGS过滤从多字段关键词改为固定subject白名单（exField5），并按全量subject统计更新过滤词；重抓后名单由14增至29且保留核心样本姓名] [如需可将SIGS subject白名单外置到配置文件并增加白名单变更审计]
- [2026-04-17] [已将SIGS subject白名单外置到 config/sigs_subject_keywords.json，并改为运行时读取配置；测试与重抓通过，SIGS名单维持29人] [后续可为关键词配置增加文档说明和变更流程]
- [2026-04-17] [完成清华任务0整体进展总结并同步 README/task_card/task1-progress 文档与 repo memory；新增“任务1前置老师预过滤以节省API配额”待办] [后续实现预过滤策略并评估配额节省效果]
- [2026-04-17] [根据任务2前置预筛需求，重整任务拆分并将任务0契约升级为“姓名+详情URL 双采集（teacher_profiles）”文档方案，补齐任务卡与规则驱动验收标准] [后续按新契约实现 teacher_list_collector 与提取器返回 name+profile_url 并完成兼容验证]
- [2026-04-17] [基于人工智能学院页面卡片示例，进一步将任务0策略升级为“自动整页识别优先，站点规则兜底”，并将 teacher_profiles 目标字段扩展为 name/profile_url/email/interests/title/source_url，同步 README/task_descs/task0 文档定位] [后续实现页面探针与富字段抽取，并以清华页面做回归验证]
- [2026-04-18] [完成北大重点院系师资页在线校验（状态码/title/样本命中）并新增 docs/task0/pku_teachar_page.md 记录；同步标注 AAIS 当前网络可达性受限] [后续按该记录将北大院系逐步接入 source_urls 与提取规则回归]
- [2026-04-18] [完成上海交通大学5个关键院系教师页校验并新增 docs/task0/sjtu_teachar_page.md；补充人工智能研究院(ai)与人工智能学院(soai)机构区分与采集建议] [后续可将 SJTU 来源同步到 source_urls.json 并执行规则回归抓取]
- [2026-04-18] [完成 SJTU 计算机学院主入口 AJAX 抓取修复并同步 README/task_descs/task0/task1 文档口径；将下一优先计划设定为“老师主页信号 + Google Scholar 结构化信息融合，产出可用参考与推荐”] [下一步细化融合特征与排序方案后再进入实现]
- [2026-04-19] [按任务1进度计划完成离线预筛实现：新增硬过滤（已联系/负向证据）、加权评分、A/B/C 分层、top_n+budget 裁剪，并在 teacher_list_collector 接入 --prescreen 参数与 prescreen.json 落盘，补齐单测和 README 文档] [下一步将 top_candidates 接入任务2 Scholar 抓取链路并补充同名消歧校验]
- [2026-04-19] [完成 teacher_list_core 第二轮拆分：新增 teacher_list_models/teacher_list_helpers，抽离数据结构与通用解析逻辑，core 收敛为抓取编排层；同步调整 io/prescreen/extractors 导入并通过 teacher_list_collector 回归测试] [下一步继续评估是否将 fetch_html/规则选择进一步拆为 network + pipeline 子模块]
- [2026-04-19] [将离线预筛打分常量外置到 config/prescreen_scoring.json，并在 teacher_list_prescreen 运行时加载+强校验；新增可配置回归测试] [下一步可将 task1→task2 批量闭环编排串起来，并补齐 author_id 同名消歧]
- [2026-04-19] [新增 docs/task1/batch_closed_loop_plan.md，固化“批量闭环缺失项→模块拆分→验收标准”的下一步方向] [下一步按文档顺序先实现 author_id 候选消歧，再串联批量编排与最终推荐落盘]
- [2026-04-19] [按确认口径实现 author_id 首候选两层校验（缓存反查冲突 + Scholar 主页姓名一致性），并补齐 skip reason 与单测覆盖，同时同步 README/progress 文档] [下一步将两层 skip 状态接入批量闭环编排并生成 final_recommendations 的失败明细]
- [2026-04-19] [按用户确认更新文档实施顺序：先单老师闭环（2/3/4）再做批量编排（1），并同步 batch_closed_loop_plan/progress/README] [下一步先实现单老师 recommendation 输出与失败明细，再进入批量聚合]
- [2026-04-19] [按 docs/task1/batch_closed_loop_plan.md 落地批量闭环：新增 batch_closed_loop/author_disambiguation/scholar_batch_runner/recommendation_assembler，并补齐 tests/test_batch_closed_loop.py 与 README/task1-progress/task_descs 文档同步] [下一步细化 recommendation_reason 与 risk_flags 规则，并补充端到端回归样例]
- [2026-04-19] [新增 docs/error_codes.md，整理当前代码中的显式抛错点、skip_reason 以及网络透传异常并统一错误编码] [下一步可在运行日志中补充 error_code 字段并将失败明细结构化输出]
- [2026-04-19] [按 docs/task_card_template.md 新增批量抓取实施任务卡 docs/task1/batch_fetch_task_card.md，明确多老师容错、重试与验收命令] [下一步按任务卡分步实现“单老师失败不阻塞整批”]
- [2026-04-19] [从 docs/task1/batch_fetch_task_card.md Step2 开始实施：batch_closed_loop 改为老师级容错继续执行，单老师异常不再中断整批；补齐对应单测并通过] [下一步实现 Step3 的网络最小重试与失败明细增强]
- [2026-04-19] [继续实现 Step3：author_id_resolver 与 scholar_client 的外部请求增加重试2次（共3次）和递增超时策略；补齐重试单测并通过批量回归] [下一步可细化失败明细中的 error_code/stage 结构并做真实样本冒烟]
- [2026-04-20] [实现 teacher_profile_scraper.py 教师详情页抓取模块，提取 research_fields/bio/email/title/representative_works/personal_homepage/recruiting_status/conferences；新增 full_text 字段存完整清洗文本] [下一步将 scraper 接入完整工作流并验证预筛评分效果]
- [2026-04-20] [诊断并修复预筛评分区分度低的根因：collector --prescreen 每次重新采集覆盖 scraper 写入的 homepage 数据；新增 --prescreen-dir 模式从磁盘读取 teachers.json 做预筛，解耦采集与预筛三步骤] [下一步跑完整流程验证评分改善]
- [2026-04-20] [增强 scraper：full_text 存储、extract_title 提取职称并回填、EMAIL_PATTERN 放宽域名限制；北大 AI 114人全成功（106人补全email/112人补全title），CS 119/120成功] [下一步可优化 nav 噪音过滤和 email 提取率]
- [2026-04-20] [优化详情页文本清洗：html_to_text 先删 script/style 块；clean_text 增加去重策略（出现≥2次的行视为 nav 去掉）+ nav 关键词扩展 + 短行块过滤 + homepage 跨行提取 + 去掉域名白名单限制] [已同步更新 architecture.md 任务0.5流程、数据契约、设计决策、目录结构]
- [2026-04-20] [对全部 16 个学院 1480 位教师完成详情页抓取：homepage 1329(89.8%), email 975(65.9%), title 1033(69.8%), 0 失败；上交 email 补全率最高(99%), 清华 CS 74%, 北大 CS 仅 1%(图片邮箱)] [下一步可对全部数据跑 --prescreen-dir 并分析跨校分数分布]