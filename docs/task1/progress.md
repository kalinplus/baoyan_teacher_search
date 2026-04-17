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
- 清华大学::唐杰 仍存在跨学校同名误匹配风险（单位显示为 South China University of Technology）。
- 当前版本按“首个匹配”策略运行；姓名/学校不一致时继续尝试下一个候选的逻辑暂未启用。
- 任务0产出的老师数量较大，任务1批量执行前需要先做预过滤（如按导师类别/职称/关键词/活跃度），否则 API 调用次数可能超配额。

## Step3 执行记录
- 集成完成: src/scholar_client.py 已接入 AuthorIdResolver（author_id 可选输入，缺省自动发现）。
- 文档同步: README.md、docs/task_descs.md、AGENT.md 已完成行为与命令对齐。
- 验收执行: `src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output` 成功生成 result.json 与 summary.md。
