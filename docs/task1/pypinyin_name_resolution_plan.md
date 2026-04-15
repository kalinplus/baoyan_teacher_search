# 背景
当前姓名解析与缓存逻辑位于 `src/author_id_resolver.py`，主流程调用位于 `src/scholar_client.py`。
目前系统按“用户输入原样”进行检索并作为缓存键（`{school}::{teacher}`）写入 `output/.cache/author_id_cache.json`，导致同一老师的中文名与拼音名会被分裂为两条缓存记录（例如中文名 `唐杰` 一条、`Tang Jie` 一条），影响一致性与可维护性。
本次要做的事情是：引入 `pypinyin`，将中文输入转换为拼音用于检索，同时把缓存主键统一到中文姓名；对于拼音输入保留可用性但发出警告，避免继续污染主缓存。

# 最终目标
用户输入中文姓名时，系统自动转拼音检索并统一写入中文缓存键；用户输入拼音时发出警告并继续查询，但不写入中文主缓存。

# 分步计划（有序，每步独立可验收）
Step 1: 增加姓名规范化能力（中文识别、拼音转换、复姓处理）
  - 产出物: `config/compound_surnames.json`（复姓词表）与 `src/author_id_resolver.py` 中姓名规范化函数（读取该词表并生成中文->拼音检索名）
  - 验收:
    1. 单元测试可覆盖：`周志华 -> zhi hua zhou`（或同等查询格式）
    2. 单元测试可覆盖：`欧阳娜娜 -> na na ouyang`
    3. 代码不内嵌复姓常量，复姓词表由 `config/compound_surnames.json` 读取
    4. 中文输入与 ASCII 输入可被正确区分

Step 2: 接入解析流程与缓存策略（中文缓存主键 + 拼音输入告警）
  - 产出物: `src/author_id_resolver.py` 中 `resolve`/查询构造逻辑更新；必要时补充 `tests/test_author_id_resolver.py`
  - 验收:
    1. 中文输入时：查询使用转换后的拼音姓名，缓存键写入 `{school}::{中文姓名}`
    2. ASCII 输入时：日志输出 warning，且不写入中文主缓存
    3. 既有缓存读取不回归（中文键仍可命中）

Step 3: 文档与回归验收对齐
  - 产出物: 更新 `README.md` 的“author_id 搜索行为（当前实现）”与缓存规则；补充/更新相关测试说明
  - 验收:
    1. README 与代码行为一致（中文输入->拼音检索、中文缓存主键、拼音输入告警）
    2. 测试命令执行通过（exit code 0）
    3. 最小 E2E 命令可跑通并产出 `result.json` 与 `summary.md`

# 非目标
- 不修改 `result.json` 既有字段契约（除非单独评审并明确批准）
- 不跨步骤顺手优化（例如同名消歧策略升级、候选重排序策略升级）
- 新依赖需先确认（本次仅计划引入 `pypinyin`，已获当前需求确认）

# 参考
- 项目统一规范: `AGENT.md`
- 运行与行为说明: `README.md`
- 现有解析实现: `src/author_id_resolver.py`
- 主流程入口: `src/scholar_client.py`
- 现有测试: `tests/test_author_id_resolver.py`
- 阶段任务说明: `docs/task_descs.md`

# 自动化验收命令
- 运行环境: conda 环境 `baoyan`
- 执行命令格式: `conda run -n baoyan python ...`

每步完成后可直接运行以下命令验收：
Step1:
```bash
conda run -n baoyan python -m unittest tests.test_author_id_resolver.TestAuthorIdResolverTeacherNameNormalization
```

Step2:
```bash
conda run -n baoyan python -m unittest tests.test_author_id_resolver.TestAuthorIdResolverTeacherInputWarnings
conda run -n baoyan python -m unittest tests.test_author_id_resolver.TestAuthorIdResolverCacheIsolation
```

Step3:
```bash
conda run -n baoyan python -m unittest tests.test_author_id_resolver
conda run -n baoyan python src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output
conda run -n baoyan python -c "import json,pathlib;p=pathlib.Path('output/清华大学/夏树涛/result.json');d=json.loads(p.read_text(encoding='utf-8'));print(d.get('name'))"
```

# 成功条件
- 所有步骤验收命令通过（exit code 0）
- diff 范围在预期模块内（`src/author_id_resolver.py`、`tests/test_author_id_resolver.py`、`README.md`、依赖声明文件）
- 在回归小样本上不出现明显倒退（已有中文输入样例仍可命中有效 author_id）

# 错误处理约定
- 如某步失败：先分析原因，给出修复方案，等确认后再修
- 如连续两次失败：停下来，列出可能原因，不要继续盲目重试
- 如遇到环境/依赖问题：报告具体报错，不要自行修改环境配置
