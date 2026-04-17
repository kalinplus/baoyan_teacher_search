### 背景
任务0位于教师数据获取入口，代码集中在 `src/teacher_list_collector.py`、`src/teacher_list_core.py` 与 `src/teacher_extractors/thu.py`。
当前已能稳定产出姓名列表，但对列表页中可直接提取的主页、邮箱、兴趣、职称利用不足，导致任务1预筛仍需重复请求页面，增加复杂度。
需要将任务0升级为“自动整页识别优先 + 站点规则兜底”的富字段采集流程。

### 最终目标
任务0输出在保持 `teachers` 兼容的前提下，新增可直接用于预筛的 `teacher_profiles` 富字段数据。

### 分步计划（有序，每步独立可验收）
Step 1: 升级任务0输出契约与核心数据流
  - 产出物: `src/teacher_list_core.py` 中统一的教师条目结构与落盘逻辑
  - 产出物: `src/teacher_list_collector.py` 对新结构的组装与输出
  - 验收: 生成的 `teachers.json` 同时包含 `teachers` 与 `teacher_profiles`，且 `teacher_profiles` 每项包含 `name/profile_url/email/interests/title/source_url`（允许 `null` 或空数组）

Step 2: 一次性实现“AI分析HTML -> 生成提取逻辑 -> 代码化执行”的通用能力（规则兜底）
  - 产出物: `src/teacher_list_core.py` 的页面探针、候选块识别、字段提取主流程
  - 产出物: `src/teacher_extractors/thu.py` 的规则兜底接口（仅自动流程失败时触发）
  - 产出物: Step2 的实现说明文档（输入HTML特征、字段判定逻辑、兜底触发条件）
  - 验收: Step2仅建设一次；后续新增学院只需复用同一代码流程。对至少 1 个未手工标注结构的学院页可直接提取 `profile_url`，并抽取部分 `email/interests/title`

Step 3: 导出与测试联动，保障回归
  - 产出物: `src/teacher_list_core.py` 中 `export_jsonl` 包含 `profile_url`（有则可附加 `email/interests/title`）
  - 产出物: `tests/test_teacher_list_collector.py` 新增富字段与兼容性测试
  - 验收: 单测通过；`all_teachers.jsonl` 可被逐行读取且包含 `school/teacher/profile_url`

### 非目标
- 不在本任务中接入 Google Scholar 查询流程
- 不跨步骤顺手重构无关模块
- 新依赖需先确认
- 不改变 `result.json` 现有字段契约

### 参考
- `docs/task_descs.md`
- `docs/task0/step2_rule_driven_strategy.md`
- `src/teacher_list_collector.py`
- `src/teacher_list_core.py`
- `src/teacher_extractors/thu.py`
- `tests/test_teacher_list_collector.py`

### 自动化验收命令
- 运行环境: conda 环境 `baoyan`
- 执行命令格式: `conda run -n baoyan python xxx`

每步完成后可直接运行以下命令验收：
Step1:
```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 清华大学 --college 人工智能学院 --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/清华大学/人工智能学院/teachers.json','r',encoding='utf-8'));t=d.get('teachers',[]);p=d.get('teacher_profiles',[]);need={'name','profile_url','email','interests','title','source_url'};ok=len(t)>0 and len(p)==len(t) and all(need.issubset(set(i.keys())) for i in p);print(ok)"
```

Step2:
```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 清华大学 --college 软件学院 --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/清华大学/软件学院/teachers.json','r',encoding='utf-8'));p=d.get('teacher_profiles',[]);print(any(i.get('profile_url') for i in p))"
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 清华大学 --college 人工智能学院 --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/清华大学/人工智能学院/teachers.json','r',encoding='utf-8'));p=d.get('teacher_profiles',[]);print(any(i.get('email') or i.get('interests') or i.get('title') for i in p))"
```

Step3:
```bash
conda run -n baoyan python -m unittest tests.test_teacher_list_collector
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --export-jsonl output/teacher_pool/all_teachers.jsonl
conda run -n baoyan python -c "import json,pathlib;lines=pathlib.Path('output/teacher_pool/all_teachers.jsonl').read_text(encoding='utf-8').splitlines();print(len(lines)>0 and all({'school','teacher','profile_url'}.issubset(set(json.loads(x).keys())) for x in lines))"
```

### 成功条件
- 所有步骤验收命令通过（exit code 0）
- diff 范围在 `src/teacher_list_*`、`src/teacher_extractors/thu.py`、`tests/test_teacher_list_collector.py` 与任务0文档内
- 在清华样例页上新增字段可落盘，且 `teachers` 旧字段保持可用

### 错误处理约定
- 如某步失败：先分析失败页面结构与提取路径，给出最小修复方案，确认后再改
- 如连续两次失败：停下来，列出自动识别与规则兜底的候选方案并等待确认
- 如遇到环境/依赖问题：报告具体报错，不自行修改全局环境配置
