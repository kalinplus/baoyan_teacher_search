# CLAUDE.md

本文件是本仓库的统一代理入口说明（类似 CLAUDE.md）。

## Project Guidelines

### Code Style
- 使用 Python 进行实现，保持函数和类命名清晰、职责单一。
- 变更时优先保持输出字段契约稳定，避免随意增删 result.json 字段。
- 仅在必要时添加注释，注释应解释业务意图而不是逐行复述代码。

### Architecture
- 主要运行入口：`src/teacher_list_collector.py`（采集）、`src/llm/pipeline.py`（LLM 提取+匹配）。
- ~~`src/scholar/scholar_client.py`~~（已废弃，Google Scholar 链路不再维护）。
- 学校归一化配置来自 config/universities.json。
- LLM Pipeline 输出目录结构：`output/teacher_pool/{学校}/{学院}/recommendations.json` 与 `html_report/`。

### Build and Test
- 安装依赖: pip install -r requirements.txt
- ~~运行命令: python src/scholar/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output~~（已废弃）
- ~~快速验收: python -c "import json,pathlib;p=pathlib.Path('output/清华大学/夏树涛/result.json');d=json.loads(p.read_text(encoding='utf-8'));print(d.get('name'))"~~（已废弃）
- 当前推荐运行: python src/llm/pipeline.py --input output/teacher_pool/{学校}/{学院}/teachers.json --resume ./resume.txt --interests ./interests.txt --output-dir output/推荐结果
- 当前仓库未配置单元测试框架；改动后至少执行一次运行命令和一次输出校验。

### Conventions
- ~~必须提供环境变量 SERPAPI_KEY~~（已废弃，随 Scholar 链路移除）。
- 必须提供环境变量 SILICONFLOW_API_KEY（LLM Pipeline 需要）。
- school 参数必须能在 config/universities.json 中归一化，否则会抛出 ValueError。
- ~~默认支持学校+老师自动发现 author_id；也允许显式传入 author_id。~~（已废弃）
- ~~自动发现依赖 SCRAPERAPI_KEY。~~（已废弃）

### Personal Engineering Preferences
1. Fail fast and loudly: Do not write fallback logic unless it is explicitly required.
2. Let exceptions/errors bubble up early: Do not handle errors inside business layers.
3. Valid test principle: Prove a bug/problem exists by making it fail first. Tests that only pass prove little.

### Docs
- 项目运行与字段契约: README.md
- 阶段任务描述: docs/task_descs.md
- 架构与数据契约: docs/architecture.md
- ~~阶段2进度~~ / ~~问题归档~~（文件不存在，已清理）
- ~~Step1契约~~ / ~~批量闭环计划~~ / ~~LLM Pipeline 设计~~ / ~~技术路线背景~~（已归档至 docs/archive/）

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

<!-- 迁移至 .claude/memory.md，按 Current Focus / Active Decisions / Known Issues / Recent Progress / Next Priority 结构整理 -->
<!-- 每次 session 结束前更新 .claude/memory.md 即可 -->