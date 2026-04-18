### 背景
任务0当前已在清华页面完成基础验证，但上海交通大学院系页面结构更异构：
- 同一学校内同时存在中文静态页、英文目录页、卡片页与旧版入口。
- 计算机学院主页 `jiaoshiml.html` 可达但姓名命中不稳定，需保留 CSE 旧页 `People.aspx` 兜底。
- 人工智能学院（`soai.sjtu.edu.cn`）与人工智能研究院（`ai.sjtu.edu.cn`）是不同机构，当前应按“可抓取性优先”先接入前者。

本任务卡按 `docs/task0/step2_rule_driven_strategy.md` 的“自动整页识别优先 + 站点规则兜底”路线，落地 SJTU 教师列表抓取。

### 最终目标
在保持 `teachers` 兼容的前提下，面向 SJTU 重点院系稳定输出 `teacher_profiles` 富字段：
- 每条包含 `name/profile_url/email/interests/title/source_url`（允许空值，不允许缺字段）。
- 自动流程失败时触发站点兜底，失败显式抛错，不静默写空名单。

### SJTU 目标页面范围（本轮）
- 上海交通大学 / 人工智能学院（当前最高优先级，先适配）
  - 主入口: `https://soai.sjtu.edu.cn/cn/faculty/zzjs`
  - 补充入口: `https://soai.sjtu.edu.cn/cn/teacher/spkz`
- 上海交通大学 / 计算机学院（网络空间安全学院、密码学院）
  - 主入口: `https://www.cs.sjtu.edu.cn/jiaoshiml.html`
  - 兜底入口: `https://cs.sjtu.edu.cn/cse/People.aspx`
- 上海交通大学 / 浦江国际学院（原密西根学院）
  - `https://gc.sjtu.edu.cn/about/faculty-staff/faculty-directory/`
- 上海交通大学 / 溥渊未来技术学院
  - `https://gift.sjtu.edu.cn/faculty`

说明：人工智能研究院（`https://ai.sjtu.edu.cn`）本轮仅保留机构入口记录，不纳入“必须通过”的稳定抓取清单。

### 分步计划（有序，每步独立可验收）
Step 1: 先适配人工智能学院（当前最先使用）
  - 产出物: `docs/task0/source_urls.json` 新增上海交通大学人工智能学院主/补充入口（补充入口使用独立学院名 `人工智能学院（双聘/客座）`，避免输出覆盖）
  - 产出物: `src/teacher_list_collector.py` 跑通后输出 `teachers` + `teacher_profiles`
  - 验收: `output/teacher_pool/上海交通大学/人工智能学院/teachers.json` 中 `teacher_profiles` 字段齐全，且与 `teachers` 数量对齐

Step 2: 再扩展 SJTU 其余异构页面（自动优先，规则兜底）
  - 产出物: `src/teacher_list_core.py` 自动探针流程在 SJTU 页可直接提取 `profile_url`
  - 产出物: `src/teacher_extractors/` 中 SJTU 兜底规则（仅自动流程失败或质量劣化时启用）
  - 产出物: `docs/task0/step2_rule_driven_strategy.md` 对应触发条件与质量门禁保持一致
  - 验收:
    - 人工智能学院页面可命中至少部分 `email/interests/title`
    - 计算机学院页面在主入口不足时可使用 CSE 旧页兜底入口（配置为独立学院名，避免覆盖主入口产物）

Step 3: 导出联动与回归保障
  - 产出物: `src/teacher_list_core.py` 的 `export_jsonl` 保留 `profile_url` 与富字段
  - 产出物: `tests/test_teacher_list_collector.py` 覆盖 SJTU 兼容性与富字段断言
  - 验收: 单测通过，`all_teachers.jsonl` 可逐行读取并含 `school/teacher/profile_url`

### 非目标
- 不在本任务中接入 Google Scholar 查询流程
- 不引入浏览器自动化（仅当 requests 无法覆盖时再单独审批）
- 不跨步骤重构无关模块
- 不改变 `result.json` 既有字段契约

### 参考
- `docs/task_descs.md`
- `docs/task0/step2_rule_driven_strategy.md`
- `docs/task0/teachar_pages/sjtu_teachar_page.md`
- `docs/task0/source_urls.json`
- `src/teacher_list_collector.py`
- `src/teacher_list_core.py`
- `src/teacher_extractors/`
- `tests/test_teacher_list_collector.py`

### 自动化验收命令
- 运行环境: conda 环境 `baoyan`
- 执行命令格式: `conda run -n baoyan python xxx`

每步完成后可直接运行以下命令验收：

Step1:
```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/上海交通大学/人工智能学院/teachers.json','r',encoding='utf-8'));t=d.get('teachers',[]);p=d.get('teacher_profiles',[]);need={'name','profile_url','email','interests','title','source_url'};ok=len(t)>0 and len(p)==len(t) and all(need.issubset(set(i.keys())) for i in p);print(ok)"
```

Step2:
```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/上海交通大学/人工智能学院/teachers.json','r',encoding='utf-8'));p=d.get('teacher_profiles',[]);print(any(i.get('email') or i.get('interests') or i.get('title') for i in p))"
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 计算机学院（网络空间安全学院、密码学院） --out-dir output/teacher_pool
conda run -n baoyan python -c "import json;d=json.load(open('output/teacher_pool/上海交通大学/计算机学院（网络空间安全学院、密码学院）/teachers.json','r',encoding='utf-8'));p=d.get('teacher_profiles',[]);print(any(i.get('profile_url') for i in p))"
```

Step3:
```bash
conda run -n baoyan python -m unittest tests.test_teacher_list_collector
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --export-jsonl output/teacher_pool/all_teachers.jsonl
conda run -n baoyan python -c "import json,pathlib;lines=pathlib.Path('output/teacher_pool/all_teachers.jsonl').read_text(encoding='utf-8').splitlines();ok=len(lines)>0 and all({'school','teacher','profile_url'}.issubset(set(json.loads(x).keys())) for x in lines);print(ok)"
```

### 成功条件
- 所有步骤验收命令通过（exit code 0）
- diff 范围控制在 `docs/task0/*`、`src/teacher_list_*`、`src/teacher_extractors/*`、`tests/test_teacher_list_collector.py`
- 人工智能学院（`soai.sjtu.edu.cn`）优先适配并先通过验收，再推进其他学院
- SJTU 学院页可稳定落盘 `teachers` 与 `teacher_profiles`，并满足非空、去重、字段完整性

### 错误处理约定
- 如某步失败：先定位页面结构与提取路径，给出最小修复方案后再改
- 如连续两次失败：暂停实现，列出自动识别与兜底规则候选方案，等待确认
- 如遇环境/依赖问题：报告具体报错，不自行修改全局环境配置
