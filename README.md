# 保研导师信息抓取（阶段2：最小可运行）

本仓库当前实现了阶段2最小闭环：

- 输入学校和老师姓名（可选显式 author_id）
- 归一化学校名称
- 自动发现或使用显式 author_id 后拉取老师基础学术信息
- 标准目录输出 `result.json` 与 `summary.md`

## 运行前准备

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量（可用 `.env`）

- `SCRAPERAPI_KEY`（自动发现 author_id 时需要）
- `SERPAPI_KEY`

## CLI 入口

唯一入口脚本：`src/scholar_client.py`

执行示例：

```bash
conda run -n baoyan python src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output
```

显式 author_id 模式（可选）：

```bash
conda run -n baoyan python src/scholar_client.py --school 南大 --teacher 周志华 --author-id rSVIHasAAAAJ --out-dir output
```

仅获取 author_id 过程，且开启详细日志（便于排查 author_id 获取过程）：

```bash
conda run -n baoyan python src/author_id_resolver.py --school 清华 --teacher 夏树涛 --out-dir output --log-level DEBUG
```

## 输出路径

默认输出到：

- `output/{学校全称}/{老师姓名}/result.json`
- `output/{学校全称}/{老师姓名}/summary.md`

## author_id 搜索行为（当前实现）

- 查询模板仅使用一次：`site:scholar.google.com/citations {学校英文缩写} {老师检索词}`。
- 学校词仅使用英文缩写（如 `THU`、`PKU`），不再尝试多个学校别名。
- 老师输入若包含中文：会使用 `pypinyin` 自动转为“名在前、姓在后”的拼音检索词（如 `周志华 -> Zhihua Zhou`、`欧阳娜娜 -> Nana Ouyang`）。
- 复姓词表由 `config/compound_surnames.json` 提供，代码运行时读取该配置。
- 老师输入若不包含中文（如直接输入拼音）：会输出 warning，并继续按原输入检索。
- 缓存主键统一为中文姓名：仅中文输入会写入 `author_id_cache.json`（键格式 `{学校全称}::{中文姓名}`）；非中文输入为避免混合键污染不写缓存。
- 仅抓取 Google 搜索第 1 页（`start=0`）。
- 解析网页文本中第一个正则匹配到的 `author_id` 作为最终结果。
- 候选 `author_id` 最多抓取 1 个（命中首个有效候选后立即停止），不再抓取 10 个。
- 命中首候选后执行两层校验：
	- 先做 author_id 反查冲突：若该 author_id 已绑定到其他老师姓名，标记并跳过（`skip_reason=author_id_conflict_existing_teacher`）。
	- 再做 Scholar 主页姓名校验：若主页姓名与当前检索老师不一致，标记并跳过（`skip_reason=scholar_name_mismatch`）。
- 仅当两层校验都通过时，才写入缓存并返回结果。
- 支持 `--log-level` 输出调用链日志，建议排障时使用 `DEBUG`。

## 最小字段契约

`result.json` 包含以下阶段2核心字段：

- `author_id`
- `name`
- `affiliations`
- `email`
- `interests`
- `citations_all`
- `citations_last_1y`
- `citations_last_3y`
- `citations_last_5y`
- `publications_total`
- `publications_last_1y`
- `publications_last_3y`
- `publications_last_5y`
- `publications_truncated`
- `h_index_all`
- `i10_index_all`
- `source`
- `matched_school`
- `matched_teacher`

附加字段：

- `publications_truncated=true` 表示当前发文统计可能被单次抓取窗口截断（存在下一页）；`false` 表示当前请求未检测到下一页

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

关键词白名单配置：

- `config/sigs_subject_keywords.json`

当前抓取结果（teachers 数，基于 `output/teacher_pool`）：

- 上海交通大学 人工智能学院：38
- 上海交通大学 计算机学院（网络空间安全学院、密码学院）：293
- 上海交通大学 浦江国际学院（原密西根学院）：65
- 上海交通大学 溥渊未来技术学院：64
- 清华大学 计算机科学与技术系：191
- 软件学院：41
- 人工智能学院：13
- 交叉信息研究院：75
- 网络科学与网络空间研究院：110
- 自动化系：103
- 电子工程系：147
- 深圳国际研究生院（计算机科学与技术方向）：87

下一步优先计划（已设定，具体实现后续讨论）：

- 顺序一：先打通单老师闭环（已实现两层 skip 校验，下一步补齐单老师 recommendation 输出与失败明细）。
- 顺序二：单老师闭环稳定后，再做批量编排，读取 prescreen top_candidates 执行批量抓取与汇总。
- 顺序三：增强推荐汇总规则，细化 recommendation_reason 与 risk_flags。

执行示例：

```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool
```

输出路径：

- `output/teacher_pool/{学校}/{学院}/teachers.json`

可选导出任务1批量输入：

```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool --export-jsonl output/teacher_pool/all_teachers.jsonl
```

离线预筛（任务1前置控量）：

```bash
conda run -n baoyan python src/teacher_list_collector.py --input docs/task0/source_urls.json --school 上海交通大学 --college 人工智能学院 --out-dir output/teacher_pool --prescreen --top-n 20 --budget 20 --keywords 机器学习,计算机视觉
```

预筛参数说明：

- `--prescreen`：开启离线预筛。
- `--top-n`：进入下一阶段的目标候选数。
- `--budget`：实际预算上限（最终候选数为 `min(top_n, budget)`）。
- `--keywords`：方向关键词（逗号分隔），用于兴趣匹配加分。
- `--contacted-list`：已联系名单配置路径（默认 `config/contacted_teachers.json`）。

预筛打分规则配置：

- `config/prescreen_scoring.json`：离线预筛的可调参数文件。
- 可直接调整负向关键词、证据字段、职称关键词、各项加减分权重与 A/B/C 阈值，无需改动代码。

开启预筛后会额外输出：

- `output/teacher_pool/{学校}/{学院}/prescreen.json`

`prescreen.json` 关键字段：

- `top_candidates`：按分数排序且通过预算裁剪后的候选（用于后续 Scholar 抓取）。
- `candidates`：所有未被硬跳过的评分结果（含 `score/tier/reasons`）。
- `skipped`：被跳过条目（`skip_reason` 包含 `already_contacted`、`negative_signal_evidence`、`over_budget`）。
- `stats`：总量、分层分布与各类跳过统计。

任务1批量闭环（prescreen Top N -> author_id -> scholar -> recommendation）：

```bash
conda run -n baoyan python src/batch_closed_loop.py --school 清华大学 --college 计算机科学与技术系 --pool-dir output/teacher_pool --out-dir output
```

批量闭环输入：

- `output/teacher_pool/{学校}/{学院}/teachers.json`
- `output/teacher_pool/{学校}/{学院}/prescreen.json`

批量闭环输出：

- `output/{学校}/{学院}/final_recommendations.json`

`final_recommendations.json` 关键字段：

- 顶层字段：`school`、`college`、`generated_at`、`total_candidates`、`resolved_candidates`、`failed_candidates`、`failed_candidate_details`、`recommendations`
- `failed_candidate_details`：失败老师维度明细，当前包含消歧阶段 skip 原因（`author_id_conflict_existing_teacher`、`scholar_name_mismatch`）
- `recommendations` 单项字段：`teacher`、`prescreen_score`、`prescreen_tier`、`prescreen_reasons`、`author_id`、`author_id_source`、`scholar_metrics`、`recommendation_reason`、`risk_flags`

## 自动化验收命令

- Step1

```bash
conda run -n baoyan python -c "print('contract-reviewed')"
```

- Step2

```bash
conda run -n baoyan python src/author_id_resolver.py --school 清华 --teacher 夏树涛 --out-dir output
```

- Step3

```bash
conda run -n baoyan python src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output
conda run -n baoyan python -c "import json,pathlib;p=pathlib.Path('output/清华大学/夏树涛/result.json');d=json.loads(p.read_text());print(d.get('name'))"
```

## 阶段文档索引

- 任务描述: docs/task_descs.md
- 阶段2进度: docs/stage2/progress.md
- Step1契约: docs/task1/step1_contract.md
- 问题归档: docs/archive/stage2_issues.md

