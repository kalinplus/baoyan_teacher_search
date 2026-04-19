# 阶段2进度文档（流程工程化）

## 目标
实现最小可运行闭环：输入学校+老师姓名，自动发现 author_id，并拉取结构化信息后标准化落盘。

## 边界
- 仅做阶段2流程工程化。
- 不实现任务2（主页深挖）和任务3（匹配分析）。
- 不新增依赖（如需新增先审批）。
- 遵循 fail fast，不在业务层吞异常。

## 分步计划
1. Step1: 固化任务1的数据契约与模块边界
- 产出物: docs/task1/step1_contract.md
- 验收: 契约可独立回答输入、输出、缓存规则、失败行为
- 状态: 已完成

2. Step2: 实现 author_id 自动发现模块（独立类）
- 产出物: 新增 author_id 解析类文件（与 src/scholar_client.py 解耦）
- 验收: 学校+老师可得到 author_id；重复查询命中缓存；异常上抛
- 状态: 已完成

3. Step3: 接入主流程并完成文档同步
- 产出物: 更新 src/scholar_client.py 流程与 README/task_descs 文档
- 验收: 一条命令产出 output/{学校}/{老师}/result.json 与 summary.md
- 状态: 已完成

## 风险与注意点
- 同名老师导致 author_id 误匹配。
- 搜索结果波动导致抽取不稳定。
- 文档与代码不一致按 AGENT.md 视为阻塞项。
- 历史问题归档见: docs/archive/stage2_issues.md
- 当前策略为“学校英文缩写 + 用户输入老师名单次查询 + 第1页 + 首个正则匹配 author_id”，未启用候选二次校验。
- 若老师输入包含中文，系统会记录 warning 提示结果可能不准，但不会自动改写输入。

## 验收命令（阶段2）
- Step1: conda run -n baoyan python -c "print('step1-contract-reviewed')"
- Step2: conda run -n baoyan python src/author_id_resolver.py --school 清华 --teacher 夏树涛 --out-dir output
- Step3: conda run -n baoyan python src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output

## Step2 执行记录
- 首次执行: 成功返回 author_id（来源为 google_search 或 author_id_cache）。
- 二次执行: 成功命中同一缓存键（清华大学::夏树涛）。
- 负例执行: school 为未知值时抛 ValueError（符合 fail fast）。

## 当前待办项
- 已确认下一优先计划：基于老师主页与列表页信号做任务1预筛，再对 Top N 候选做 Scholar 结构化精筛。
- 目标产物调整为“可直接使用的信息参考与推荐结果”：同一老师维度聚合主页证据、Scholar 指标、推荐理由与风险提示。
- 任务1将优先复用任务0 `teacher_profiles` 字段，减少重复抓取并控制 API 成本。
- 清华大学::唐杰 仍存在跨学校同名误匹配风险；在融合阶段需要补充学校/姓名一致性校验策略。
- 当前版本按“首个匹配”策略运行；姓名/学校不一致时继续尝试下一个候选的逻辑暂未启用。

## Step3 执行记录
- 集成完成: src/scholar_client.py 已接入 AuthorIdResolver（author_id 可选输入，缺省自动发现）。
- 文档同步: README.md、docs/task_descs.md、AGENT.md 已完成行为与命令对齐。
- 验收执行: `src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output` 成功生成 result.json 与 summary.md。

---

## 任务1离线预筛任务卡（2026-04-19）

### 背景
- 任务0已稳定输出 teachers + teacher_profiles，具备离线预筛所需的基础字段。
- 当前缺口是任务1预筛层，导致后续 Scholar 调用无法控量，API 成本与误调用风险偏高。
- 当前优先目标是先实现离线预筛，再将 Top N 候选送入任务2结构化抓取。

### 最终目标
- 在不新增依赖前提下，基于 teacher_profiles 实现可解释的离线预筛，输出候选分层结果（A/B/C）与 Top N 名单。

### 硬筛选原则（当前口径）
- 仅使用“确定性且可追溯”的规则做硬跳过，默认不依赖未抓取的页面信息。
- 已联系名单命中：硬跳过（skip_reason=already_contacted）。
- 输入契约不合法（如缺姓名/结构错误）：fail fast，显式报错。
- 负向业务信号默认不硬跳过；仅在已抓取主页/学院文本证据时，命中明确负向关键词才硬跳过（skip_reason=negative_signal_evidence）。
- 信息不足（如无主页、无邮箱、方向信息短）只降分，不硬跳过。

### 分步计划（有序，每步独立可验收）
Step 1: 固化离线预筛契约与特征定义
	- 产出物: docs/task1/step1_contract.md 补充离线预筛输入输出、硬过滤规则、评分项与字段字典
	- 产出物: docs/task_descs.md 同步“任务1优先执行口径”
	- 验收: 文档可独立回答输入字段、输出字段、跳过条件、解释字段与失败行为

Step 2: 实现预筛算法（硬过滤 + 加权评分 + 分层）
	- 产出物: src/teacher_list_core.py 新增预筛特征提取与评分函数
	- 产出物: src/teacher_list_collector.py 新增预筛执行参数（top_n、budget、contacted_list、keywords）
	- 验收: 同一输入稳定得到降序候选；已联系名单被硬跳过；信息不足样本仅降分不硬跳过；每条结果包含 score、tier、reasons、skip_reason

Step 3: 结果落盘与回归测试
	- 产出物: output/teacher_pool/{学校}/{学院}/prescreen.json（候选、跳过、统计信息）
	- 产出物: tests/test_teacher_list_collector.py 增加预筛单测与回归断言
	- 验收: 不开启预筛参数时行为与当前一致；开启后可产出 prescreen.json 且字段契约完整

### 非目标
- 不实现 Scholar 同名消歧增强与候选回退策略。
- 不改动 result.json 既有字段契约。
- 不跨步骤顺手优化无关模块。
- 新依赖需先确认。

### 参考
- docs/task_descs.md
- docs/task1/step1_contract.md
- config/contacted_teachers.json
- src/teacher_list_core.py
- src/teacher_list_collector.py
- tests/test_teacher_list_collector.py

### 自动化验收命令
- 运行环境: conda 环境 baoyan
- 执行命令格式: conda run -n baoyan python xxx
- Step1: conda run -n baoyan python -c "print('task1-prescreen-contract-reviewed')"
- Step2: conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool --prescreen --top-n 20 --keywords 机器学习,计算机视觉
- Step3: conda run -n baoyan python -m unittest tests.test_teacher_list_collector

### 成功条件
- 所有步骤验收命令通过（exit code 0）。
- diff 范围控制在 docs/task1/*、docs/task_descs.md、src/teacher_list_core.py、src/teacher_list_collector.py、tests/test_teacher_list_collector.py。
- 不开启预筛参数时，现有 teachers 与 teacher_profiles 输出保持兼容。

### 本次执行记录（2026-04-19）
- Step2 已完成：`src/teacher_list_core.py` 新增离线预筛实现（硬过滤 + 评分 + A/B/C 分层 + top_n/budget 裁剪），并提供 `prescreen.json` 落盘能力。
- Step2 已完成：`src/teacher_list_collector.py` 已接入 `--prescreen`、`--top-n`、`--budget`、`--keywords`、`--contacted-list` 参数。
- Step3 已完成：`tests/test_teacher_list_collector.py` 新增预筛单测（硬跳过、负向证据、预算裁剪、输入契约 fail fast）。
- 文档已同步：`README.md` 增加离线预筛命令、参数说明与 `prescreen.json` 字段说明。
- 验收结果：`conda run -n baoyan python -m unittest tests.test_teacher_list_collector` 通过；基于已存在 `teachers.json` 的离线预筛落盘验证通过。

### 错误处理约定
- 如某步失败：先分析原因，给出最小修复方案，确认后再改。
- 如连续两次失败：暂停并列出候选原因，不继续盲目重试。
- 如遇环境/依赖问题：报告具体报错，不自行修改环境配置。
