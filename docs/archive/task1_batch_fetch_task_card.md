### 背景
当前已具备批量闭环入口（`src/batch_closed_loop.py`），可以从 `prescreen.json` 的 `top_candidates` 触发 author_id 解析与 Scholar 抓取，并输出 `final_recommendations.json`。

现状问题是“批量抓取可用性”不足：
- 单个老师出现网络抖动或解析失败时，整批会被 fail fast 中断。
- 失败明细对网络类异常覆盖不足，难以做批处理复盘。
- 多老师场景下，成功/失败并存时缺少稳定的落盘保障。

因此需要在不新增依赖的前提下，补齐多老师批量抓取的工程化能力。

### 最终目标
在多老师输入下实现“可持续推进的批量抓取”：单老师失败不阻塞整批，最终稳定输出成功推荐与失败明细。

### 分步计划（有序，每步独立可验收）
Step 1: 固化批量抓取契约与失败分类
  - 产出物: `docs/task1/batch_fetch_task_card.md`（本任务卡）、`docs/task1/batch_closed_loop_plan.md`（补充失败分类与输出约定）
  - 验收: 文档可独立回答“哪些错误继续、哪些错误中断、失败明细字段结构”

Step 2: 实现批量抓取容错主流程
  - 产出物: `src/batch_closed_loop.py`（老师级别 try/continue，保留输入契约 fail fast）
  - 验收: 同一批次中个别老师失败时，程序不中断，仍生成 `final_recommendations.json`

Step 3: 实现网络抖动最小重试与失败落盘
  - 产出物: `src/author_id_resolver.py`、`src/scholar_client.py`（仅针对外部请求增加有限重试）、`src/recommendation_assembler.py`（补充失败明细）
  - 验收: 遇到瞬时网络错误时有重试行为；最终失败会进入 `failed_candidate_details`，并保留 `stage/error/skip_reason` 信息

Step 4: 回归测试与端到端冒烟
  - 产出物: `tests/test_batch_closed_loop.py`（新增“部分失败不阻塞整批”用例）、必要的文档同步（`README.md`）
  - 验收: 单测通过；在真实院系样本上成功产出 `final_recommendations.json`


### 非目标
- 不改动任务0抓取规则与名单抽取逻辑
- 不引入并发抓取/异步调度
- 不实现 GUI 或额外可视化页面
- 不跨步骤顺手优化无关模块
- 新依赖需先确认

### 参考
- `docs/task1/batch_closed_loop_plan.md`
- `docs/error_codes.md`
- `src/batch_closed_loop.py`
- `tests/test_batch_closed_loop.py`

### 自动化验收命令
- 运行环境: conda 环境 `baoyan`
- 执行命令格式: `conda run -n baoyan python xxx`

[每步完成后可直接运行以下命令验收：]
Step1:
- `conda run -n baoyan python -c "print('batch-fetch-contract-reviewed')"`

Step2:
- `conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 清华大学 --college 交叉信息研究院 --out-dir output/teacher_pool --prescreen --top-n 20 --budget 20 --keywords 机器学习,理论计算机科学,人工智能`
- `conda run -n baoyan python src/batch_closed_loop.py --school 清华大学 --college 交叉信息研究院 --pool-dir output/teacher_pool --out-dir output`

Step3:
- `conda run -n baoyan python -m unittest tests.test_batch_closed_loop`

Step4:
- `conda run -n baoyan python -m unittest tests.test_batch_closed_loop tests.test_author_id_resolver tests.test_scholar_client`
- `conda run -n baoyan python -c "import json,pathlib;p=pathlib.Path('output/清华大学/交叉信息研究院/final_recommendations.json');d=json.loads(p.read_text(encoding='utf-8'));print(d.get('resolved_candidates'), d.get('failed_candidates'))"`

### 成功条件
- 所有步骤验收命令通过（exit code 0）
- diff 范围在预期模块内（`src/batch_closed_loop.py`、`src/author_id_resolver.py`、`src/scholar_client.py`、`src/recommendation_assembler.py`、`tests/test_batch_closed_loop.py`、相关文档）
- 在多老师样本上可稳定输出成功与失败并存结果，不因单个老师失败导致整批无结果

### 错误处理约定
- 如某步失败：先分析原因，给出最小修复方案，等确认后再修
- 如连续两次失败：停下来，列出可能原因，不要继续盲目重试
- 如遇到环境/依赖问题：报告具体报错，不要自行修改环境配置
