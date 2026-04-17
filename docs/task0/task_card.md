### 背景
当前流程已经支持“学校+姓名 -> Google Scholar 结构化信息”（任务1），但缺少上游原料：指定学校+学院的教师名单。
任务0要先把“教师名单采集”做成可重复执行的步骤，为后续任务1批量跑提供稳定输入。

### 最终目标
给定“学校+学院+教师列表URL”，可批量产出该学院教师姓名清单（去重后），作为任务1输入。

### 分步计划（有序，每步独立可验收）
Step 1: 固化任务0输入契约（学校/学院/教师列表URL）
  - 产出物: `docs/task0/source_urls.example.json`（示例格式）、`docs/task0/source_urls.json`（真实输入，后续由用户维护）
  - 验收: `source_urls.example.json` 能清晰表达学校、学院、URL；`source_urls.json` 按同结构可被程序读取

Step 2: 实现教师名单抓取与清洗（按URL抓取、抽取姓名、去重）
  - 产出物: `src/teacher_list_collector.py`（任务0抓取入口）、`output/teacher_pool/{学校}/{学院}/teachers.json`
  - 验收: 对单个学院执行后生成 `teachers.json`，包含非空 `teachers` 列表，且无重复姓名

Step 2.1: 规则驱动改造（按站点适配，不追求一次通吃）
  - 产出物: `docs/task0/step2_rule_driven_strategy.md`（策略与协作模板）、`src/teacher_list_collector.py`（支持按规则抓取）
  - 验收: 至少 1 个学院页面准确抽取（导航词/分页词不进入 `teachers`）

Step 2.2: 学院级规则迭代（逐页打通）
  - 产出物: 针对每个学院页面的提取规则（可先内置在代码，后续再抽配置）
  - 验收: 每新增 1 个学院，都有独立运行记录与结果抽样复核

Step 3: 产出任务1可消费的批量输入清单
  - 产出物: `output/teacher_pool/all_teachers.jsonl`（每行至少含 `school`、`teacher`）
  - 验收: 文件可被逐行读取；随机抽样记录可追溯到对应学院来源


### 非目标
- 不在任务0中实现 Google Scholar 查询（属于任务1）
- 不跨步骤顺手优化
- 新依赖需先确认
- 不实现“万能解析器”；以稳定可复现为第一目标

### 参考
- 任务描述: `docs/task_descs.md`
- 现有主流程入口: `src/scholar_client.py`
- 现有 author_id 解析模块: `src/author_id_resolver.py`
- Step2 规则驱动方案: `docs/task0/step2_rule_driven_strategy.md`

### 自动化验收命令
- 运行环境: conda 环境 `baoyan`
- 执行命令格式: `conda run -n baoyan python xxx`

每步完成后可直接运行以下命令验收：
Step1:
```bash
conda run -n baoyan python -c "import json;d=json.load(open('docs/task0/source_urls.example.json','r',encoding='utf-8'));print(isinstance(d,list) and len(d)>=1)"
```

Step2:
```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 清华大学 --college 计算机科学与技术系 --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/清华大学/计算机科学与技术系/teachers.json','r',encoding='utf-8'));print(len(d.get('teachers',[]))>0 and len(d.get('teachers',[]))==len(set(d.get('teachers',[]))))"
```

Step3:
```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --export-jsonl output/teacher_pool/all_teachers.jsonl
conda run -n baoyan python -c "import pathlib; p=pathlib.Path('output/teacher_pool/all_teachers.jsonl'); print(p.exists() and p.stat().st_size>0)"
```

### 成功条件
- 所有步骤验收命令通过（exit code 0）
- diff 范围在预期模块内
- 产出的教师名单可直接作为任务1输入原材料

### 错误处理约定
- 如某步失败：先分析原因，给出修复方案，等确认后再修
- 如连续两次失败：停下来，列出可能原因，不要继续盲目重试
- 如遇到环境/依赖问题：报告具体报错，不要自行修改环境配置

### 当前进展（清华）
- 已完成 `docs/task0/thu_teachar_page.md` 中全部学院页面规则适配与落盘。
- 已生成目录：`output/teacher_pool/清华大学/*/teachers.json`。
- 当前数量统计：
  - 计算机科学与技术系 127
  - 软件学院 41
  - 人工智能学院 13
  - 交叉信息研究院 47
  - 网络科学与网络空间研究院 54
  - 自动化系 59
  - 电子工程系 147
  - 深圳国际研究生院（计算机科学与技术方向） 29

### 新增待办
- 任务1调用 API 前增加“老师名单预过滤”步骤，优先压缩候选老师规模，避免 API 配额不足。
