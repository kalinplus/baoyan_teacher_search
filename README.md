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

开启详细日志（便于排查 author_id 获取过程）：

```bash
conda run -n baoyan python src/author_id_resolver.py --school 清华 --teacher 夏树涛 --out-dir output --log-level DEBUG
```

显式 author_id 模式（可选）：

```bash
conda run -n baoyan python src/scholar_client.py --school 南大 --teacher 周志华 --author-id rSVIHasAAAAJ --out-dir output
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
- 当前不做候选结果二次校验（如姓名/学校校验后再取下一个）；该能力作为后续增强项。
- 可选后续 TODO（配合候选校验）：如果校验流程已用完当前搜索得到的全部候选，下一次搜索改用连字符姓名格式（如 `Zhi-Hua Zhou`）。
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
- `h_index_all`
- `i10_index_all`
- `source`
- `matched_school`
- `matched_teacher`

附加字段：

- 无

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

