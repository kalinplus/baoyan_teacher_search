# 保研导师信息抓取与推荐（全链路 CLI）

输入学校+学院，批量抓取教师池，经 homepage 详情补充后直接通过 LLM 提取研究方向与招生信息，最终输出匹配度排序的推荐报告（JSON + HTML）。

核心链路：

- **任务0**：教师名单采集（`teacher_list_collector.py`）
- **任务0.5**：教师主页详情抓取（`teacher_profile_scraper.py`）
- ~~**任务1**：离线预筛（`teacher_list_prescreen.py`）~~（已废弃，由 LLM Pipeline 替代）
- **任务3**：LLM 提取 + 匹配推荐（`llm/pipeline.py`）
- **任务4**：HTML 报告生成（`recommendations_to_html.py`）

## 运行前准备

1. 激活项目 conda 环境（所有脚本必须在此环境下运行，不要使用 base 环境）

```bash
conda activate baoyan
export PYTHONPATH=src
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置环境变量（可用 `.env`）

- `SILICONFLOW_API_KEY`（LLM 提取与匹配需要）
- ~~`SCRAPERAPI_KEY`~~ / ~~`SERPAPI_KEY`~~（已废弃，Google Scholar 链路不再维护）

## CLI 入口

主要入口脚本：

- **批量采集**：`src/teacher_list_collector.py`
- **LLM 提取 + 匹配**：`src/llm/pipeline.py`
- ~~**单老师 Scholar 抓取**：`src/scholar/scholar_client.py`~~（已废弃）

---

## ~~author_id 搜索行为（当前实现）~~（已废弃）

> Google Scholar 结构化信息抓取已不再维护。预筛后的候选直接通过 LLM Pipeline 完成匹配推荐，无需 author_id 解析。

~~- 查询模板仅使用一次：`site:scholar.google.com/citations {学校英文缩写} {老师检索词}`。~~
~~- 学校词仅使用英文缩写（如 `THU`、`PKU`），不再尝试多个学校别名。~~
~~- 老师输入若包含中文：会使用 `pypinyin` 自动转为“名在前、姓在后”的拼音检索词。~~
~~- 复姓词表由 `config/compound_surnames.json` 提供，代码运行时读取该配置。~~
~~- 缓存主键统一为中文姓名：仅中文输入会写入 `author_id_cache.json`。~~
~~- 命中首候选后执行两层校验（缓存反查冲突 + Scholar 主页姓名一致性）。~~

---

## ~~最小字段契约（`result.json`）~~（已废弃）

> 以下字段为 Google Scholar 链路的历史输出，已不再维护。当前核心输出为 `recommendations.json`（LLM Pipeline 产物）。

~~- `author_id`~~
~~- `name`~~
~~- `affiliations`~~
~~- `email`~~
~~- `interests`~~
~~- `citations_all` / `citations_last_*`~~
~~- `publications_total` / `publications_last_*`~~
~~- `h_index_all` / `i10_index_all`~~
~~- `source` / `matched_school` / `matched_teacher`~~

## 任务0 Step2（规则驱动教师名单抓取）

入口脚本：`src/teacher_list_collector.py`

当前已实现规则：

- 清华大学 计算机科学与技术系：`h2 > a`
- 清华大学 软件学院：`../faculty/*.htm` 链接文本
- 清华大学 人工智能学院：仅 `sz2(全职PI)` 到 `sz3(兼聘PI)` 区段内 `h4`
- 清华大学 交叉信息研究院：`sz1(全职教师)` + `sz8(研究系列)` 区段内 `h4`
- 清华大学 网络科学与网络空间研究院：`学术带头人` 到 `友情链接` 区段内 `.htm` 链接文本
- 清华大学 自动化系：`h4.h4s1`
- 清华大学 电子工程系：页面内 `showTitle`
- 清华大学 深圳国际研究生院（计算机科学与技术方向）：调用 `teacherHome` 接口后按 `subject(exField5)` 关键词白名单过滤
- 上海交通大学 人工智能学院：`soai` 教师卡片（`facultydetails`）提取 `name/profile_url/email/interests/title`
- 上海交通大学 人工智能学院（双聘/客座）：`soai` `spkz` 卡片页复用富字段提取并过滤导航噪音
- 上海交通大学 计算机学院（网络空间安全学院、密码学院）：主入口通过 AJAX 接口 `active/ajax_teacher_list.html` 解析教师名录，空结果回退 CSE 旧页
- 上海交通大学 计算机学院（CSE旧页兜底）：`PeopleList` 提取 `h2姓名 + PeopleDetail链接 + 研究领域`
- 上海交通大学 浦江国际学院（原密西根学院）：教师详情 URL 模式 `faculty-detail` 抽取
- 上海交通大学 溥渊未来技术学院：教师详情 URL 模式 `/faculty/{id}` 抽取
- 浙江大学 计算机科学与技术学院：教师名录页自动提取 `name/profile_url/email/title`
- 浙江大学 软件学院：教师名录页自动提取 `name/profile_url/email/title`
- 上海创智学院 学院导师：AJAX POST `/_wp3services/generalQuery` API 获取教师 JSON，提取 `name/profile_url/title/interests`
- 中国人民大学 高瓴人工智能学院：`.tutor.media` 卡片内 `<h2><a>` 提取 `name/profile_url/title`
- 南京大学 智能科学与技术学院：Sudy CMS `/_wp3services/generalQuery?queryObj=teacherHome` 接口提取 `name/profile_url/title/interests`

关键词白名单配置：

- `config/sigs_subject_keywords.json`

当前抓取结果（teachers 数，基于 `output/teacher_pool`）：

- 上海交通大学 人工智能学院：38
- 上海交通大学 计算机学院（网络空间安全学院、密码学院）：293
- 上海交通大学 浦江国际学院（原密西根学院）：65
- 上海交通大学 溥渊未来技术学院：64
- 清华大学 计算机科学与技术系：127
- 清华大学 软件学院：41
- 清华大学 人工智能学院：13
- 清华大学 交叉信息研究院：75
- 清华大学 网络科学与网络空间研究院：110
- 清华大学 自动化系：103
- 清华大学 电子工程系：147
- 清华大学 深圳国际研究生院（计算机科学与技术方向）：87
- 浙江大学 计算机科学与技术学院：~73
- 浙江大学 软件学院：~98
- 上海创智学院 学院导师：73
- 中国人民大学 高瓴人工智能学院：26
- 南京大学 智能科学与技术学院：52

执行示例：

```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool
```

输出路径：

- `output/teacher_pool/{学校}/{学院}/teachers.json`

可选导出 JSONL：

```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool --export-jsonl output/teacher_pool/all_teachers.jsonl
```

---

## ~~离线预筛（任务1前置控量）~~（已废弃）

> 预筛功能已由 LLM Pipeline 替代。全部候选直接输入 LLM 做提取与匹配打分，不再做规则预筛、A/B/C 分层和 budget 裁剪。

~~```bash~~
~~conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool --prescreen --top-n 20 --budget 20 --keywords 机器学习,计算机视觉 --negative-keywords 艺术,设计,传媒~~
~~```~~

~~预筛参数说明：~~

~~- `--prescreen`：开启离线预筛。~~
~~- `--top-n`：进入下一阶段的目标候选数。~~
~~- `--budget`：实际预算上限。~~
~~- `--keywords`：方向关键词。~~
~~- `--negative-keywords`：负向兴趣关键词。~~
~~- `--contacted-list`：已联系名单配置路径。~~

~~预筛打分规则配置：~~

~~- `config/prescreen_scoring.json`：离线预筛的可调参数文件。~~

---

## ~~任务1批量闭环（prescreen Top N -> author_id -> scholar -> recommendation）~~（已废弃）

> 随 Google Scholar 链路废弃。预筛后的候选直接通过 LLM Pipeline 完成匹配推荐。

~~```bash~~
~~conda run -n baoyan python src/batch_closed_loop.py --school 清华大学 --college 计算机科学与技术系 --pool-dir output/teacher_pool --out-dir output~~
~~```~~

~~批量闭环输出 `final_recommendations.json` 已不再维护。~~

## LLM Pipeline（任务3：匹配推荐）

基于 SiliconFlow DeepSeek-V3 API 的端到端提取+匹配，替代规则评分：

```bash
# 端到端流水线（提取 + 匹配）
conda run -n baoyan python src/llm/pipeline.py \
  --input output/teacher_pool/上海交通大学/人工智能学院/teachers.json \
  --resume ./resume.txt \
  --interests ./interests.txt \
  --output-dir output/上交AI推荐结果
```

分步执行：

```bash
# Step1: LLM 提取教师信息
conda run -n baoyan python src/llm/profile_extractor.py \
  --input output/teacher_pool/上海交通大学/人工智能学院/teachers.json \
  --output output/上交AI推荐结果/llm_enriched.json

# Step2: LLM 匹配推荐
conda run -n baoyan python src/llm/match_engine.py \
  --input output/上交AI推荐结果/llm_enriched.json \
  --resume ./resume.txt \
  --interests ./interests.txt \
  --output output/上交AI推荐结果/recommendations.json
```

环境变量：`SILICONFLOW_API_KEY`

输出：

- `llm_enriched.json`：每个教师的 `llm_basic`（职称/邮箱/研究方向/bio/招生身份）与可选的 `llm_extended`（研究总结/招生状态/代表作/奖项/学术服务）
- `recommendations.json`：按 `match_score` 排序的推荐列表，含 `match_reasons` 与 `risk_flags`

## 可视化查看推荐结果

将 `recommendations.json` 转换为可搜索/排序的 HTML：

```bash
# 批量转换 output/ 下所有推荐结果
python recommendations_to_html.py

# 只转换单个目录
python recommendations_to_html.py -i "output/上交AI推荐结果"
```

生成 `html_report/index.html`（汇总首页）与各学院详情页，浏览器直接打开即可查看。

## 自动化验收命令

- 教师名单采集

```bash
conda run -n baoyan python src/teacher_list_collector.py \
  --input docs/task0/source_urls.json \
  --school 上海交通大学 --college 人工智能学院 \
  --out-dir output/teacher_pool
```

- ~~预筛~~（已废弃，由 LLM Pipeline 替代）

```bash
# 直接走 LLM Pipeline，不对候选池做规则预筛
conda run -n baoyan python src/llm/pipeline.py \
  --input output/teacher_pool/上海交通大学/人工智能学院/teachers.json \
  --resume ./resume.txt \
  --interests ./interests.txt \
  --output-dir output/上交AI推荐结果
```

- ~~Step2~~ / ~~Step3~~（已废弃，Google Scholar 链路不再维护）

## 阶段文档索引

- 任务描述与阶段进度: docs/task_descs.md
- 架构与数据契约: docs/architecture.md
- ~~Step1契约~~ / ~~批量闭环计划~~ / ~~LLM Pipeline 设计~~（已归档至 docs/archive/）

