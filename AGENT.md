# AGENT.md

本文件是本仓库的统一代理入口说明（类似 CLAUDE.md）。

## Project Guidelines

### Code Style
- 使用 Python 进行实现，保持函数和类命名清晰、职责单一。
- 变更时优先保持输出字段契约稳定，避免随意增删 result.json 字段。
- 仅在必要时添加注释，注释应解释业务意图而不是逐行复述代码。

### Architecture
- 当前唯一运行入口是 src/scholar_client.py。
- 通过 ScholarAuthorClient 类调用 SerpApi，主方法是 query_structured_info(author_id)。
- 学校归一化配置来自 config/universities.json。
- 输出目录结构固定为 output/{学校全称}/{老师姓名}/，包含 result.json 和 summary.md。

### Build and Test
- 安装依赖: pip install -r requirements.txt
- 运行命令: python src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output
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
