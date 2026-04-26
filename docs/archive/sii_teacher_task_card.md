### 背景
上海创智学院（Shanghai Innovation Institute, sii.edu.cn）是 2024 年新成立的研究型机构，聚焦 AI 领域（具身智能、大模型、科学智能）。其教师页面 (https://www.sii.edu.cn/xyds_92/list.htm) 采用 sudy 平台 CMS，教师数据通过 AJAX POST 从后端 API 加载，HTML 源码中不含教师信息。当前提取器体系尚无 SII 规则，需新增以扩充教师池覆盖面。

### 最终目标
新增 `src/teacher_extractors/sii.py`，实现对上海创智学院导师列表的全量采集（73 位教师），产出 name + profile_url + title + interests，并通过 collector 回归验收。

### 页面技术分析
- **加载方式**：AJAX POST，非静态 HTML
- **API 端点**：`POST https://www.sii.edu.cn/_wp3services/generalQuery?queryObj=articles`
- **请求参数**：
  - `siteId=3`, `columnId=92`, `rows=999`, `pageIndex=1`
  - `returnInfos`: 指定返回字段（title, url, shortTitle, summary, content）
  - `conditions`: 筛选条件数组（可为空获取全部）
- **响应结构**（JSON）：
  ```json
  {
    "total": 73,
    "data": [
      {
        "title": "陈润楠",           // 教师姓名
        "shortTitle": "具身智能与AI系统",  // 研究方向
        "summary": "上海创智学院全职导师\n上海创智学院研究助理教授",  // 职称信息
        "url": "http://www.sii.edu.cn/2026/0416/c92a915/page.htm",  // 详情页
        "content": {"data": [{"content": "<p>...</p>"}]}  // 简介 HTML
      }
    ]
  }
  ```
- **参考实现**：`sjtu.py` 中的 `fetch_sjtu_cs_ajax_content()` 使用 `requests.post` 获取 AJAX 数据

### 分步计划（有序，每步独立可验收）

#### Step 1: 新增上海创智学院到配置文件
- 产出物: `config/universities.json` 新增条目, `docs/task0/source_urls.json` 新增条目
- 验收: `config/universities.json` 包含 `"上海创智学院": ["创智", "SII", "Shanghai Innovation Institute"]`; `source_urls.json` 包含对应条目

#### Step 2: 实现 SII 提取器 `src/teacher_extractors/sii.py`
- 产出物: `src/teacher_extractors/sii.py`
  - `supports_sii_teachers(url)` — matcher，匹配 `sii.edu.cn/xyds_92/list.htm`
  - `_fetch_sii_api(timeout)` — POST 请求 API 获取全量教师 JSON
  - `extract_sii_profiles(html, source_url)` — 调用 API 解析为 `List[TeacherProfile]`
    - `name` = `data[i].title`
    - `profile_url` = `data[i].url`（详情页绝对路径）
    - `title` = `data[i].summary`（第一行，如"上海创智学院全职导师"）
    - `interests` = `[data[i].shortTitle]`（研究领域）
    - `source_url` = 传入参数
  - `get_rules()` — 返回 `List[Rule]`
- 验收: `python -c "from teacher_extractors.sii import get_rules; print(len(get_rules()))"` 输出 1

#### Step 3: 注册提取器并运行 collector 验收
- 产出物: 修改 `src/teacher_extractors/__init__.py` 导入 sii 模块
- 验收命令:
  ```bash
  cd /Users/kalin/github/baoyan_search_teachar/src
  python -m teacher_list_collector \
    --input ../docs/task0/source_urls.json \
    --school "上海创智学院" \
    --college "学院导师" \
    --out-dir ../output/teacher_pool
  ```
  检查 `output/teacher_pool/上海创智学院_学院导师/teachers.json`：
  - 教师数量 = 73
  - 每位教师有 name / profile_url / title / interests
  - 导师类型覆盖全职/全时/分时/产业

### 非目标
- 不抓取教师详情页补充 email（API 返回中无 email 字段，详情页经抽样也无 email）
- 不实现筛选功能（导师类型/领域方向的筛选由前端 JS 完成，后端只需全量采集）
- 不新增第三方依赖（requests 已在项目中）

### 参考
- AJAX 提取模式: `src/teacher_extractors/sjtu.py` → `fetch_sjtu_cs_ajax_content()`
- 数据模型: `src/teacher_list_models.py` → `TeacherProfile`, `Rule`
- 任务卡模板: `docs/task_card_template.md`

### 自动化验收命令
- 运行环境: 系统默认 Python（项目无 conda 要求）
- 执行命令格式: python -m teacher_list_collector（在 src/ 目录下）

[Step1 完成后:]
```bash
python -c "import json; d=json.load(open('config/universities.json')); assert '上海创智学院' in d, 'SII not found'"
```

[Step2 完成后:]
```bash
cd src && python -c "from teacher_extractors.sii import get_rules; rules=get_rules(); print(f'{len(rules)} rules')"
```

[Step3 完成后:]
```bash
cd src && python -m teacher_list_collector \
  --input ../docs/task0/source_urls.json \
  --school "上海创智学院" \
  --college "学院导师" \
  --out-dir ../output/teacher_pool
# 验证输出
python -c "
import json
d = json.load(open('../output/teacher_pool/上海创智学院_学院导师/teachers.json'))
print(f'Teachers: {len(d)}')
assert len(d) == 73, f'Expected 73, got {len(d)}'
profiles = [p for p in d if p.get('profile_url')]
print(f'With profile_url: {len(profiles)}')
print(f'Sample: {d[0][\"name\"]} - {d[0].get(\"title\",\"\")} - {d[0].get(\"interests\",[])}')
"
```

### 成功条件
- 所有步骤验收命令通过（exit code 0）
- diff 范围仅在：`config/universities.json`, `docs/task0/source_urls.json`, `src/teacher_extractors/sii.py`(新增), `src/teacher_extractors/__init__.py`
- 产出 73 位教师，覆盖全职/全时/分时/产业四类导师

### 错误处理约定
- 如某步失败：先分析原因，给出修复方案，等确认后再修
- 如连续两次失败：停下来，列出可能原因，不要继续盲目重试
- 如遇到环境/依赖问题：报告具体报错，不要自行修改环境配置
- 如 API 端点不可达：记录 HTTP 状态码和响应体，暂停等待确认
