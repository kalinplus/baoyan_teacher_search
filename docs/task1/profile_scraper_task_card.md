### 背景
当前预筛（prescreen）仅基于教师列表页已有字段（name、title、interests、email）做评分，信息粒度粗。例如北大 CS 列表页 interests 仅有 `["计算机网络"]`，但教师主页包含详细研究方向、代表性论文、个人简介等丰富信息。需要先抓取教师学院主页详情，补充结构化字段，再进入预筛打分，将 234 人候选池缩减到合理规模（~50 人）。

### 最终目标
对 teachers.json 中所有有 profile_url 的教师，抓取学院主页详情页，提取研究方向、个人简介、邮箱、代表工作、外部主页、招生信息，补充回 teachers.json，供后续预筛和 LLM 分析使用。

### 分步计划（有序，每步独立可验收）

Step 1: 实现主页详情抓取模块 `teacher_profile_scraper.py`
  - 产出物: `src/teacher_profile_scraper.py`
    - `scrape_profile(url, timeout) -> dict` — 单页抓取 + 启发式提取
    - `scrape_profiles(teachers_json_path, output_path, concurrency, delay)` — 批量抓取 + 写回
  - 提取字段与启发式策略：
    - **research_fields**：定位关键词（"研究方向"/"研究领域"/"Research Interest"），取后续段落，按顿号/逗号分割为列表
    - **bio**：定位关键词（"个人简介"/"简介"），取后续段落截取前 500 字；找不到则取去导航后最长文本段落
    - **email**：正则匹配 `xxx at xxx.edu.cn`（at→@）和 `xxx@xxx.edu.cn`
    - **representative_works**：定位关键词（"代表性工作"/"代表论文"/"代表性学术论著"），取后续段落；从中提取会议/期刊名（CVPR/ICML/NeurIPS/SOSP/OSDI/IEEE Trans.*等）
    - **personal_homepage**：正则匹配 `个人主页：URL` / `Homepage: URL`
    - **recruiting_status**：定位"招收"/"招生"，正向（含"招收"且不含否定词）→ `"recruiting"`，负向（含"暂停招生"等）→ `"not_recruiting"`，未找到 → `"unknown"`
  - 容错：HTTP 非 200 或解析异常 → 该教师 `homepage` 字段为 null，不阻塞批量
  - 缓存：已抓取且成功的教师不重复请求（基于输出文件中已有记录判断）
  - 并发：max_workers=3，请求间隔 delay=0.5s
  - 验收: 对北大 CS（120 人）+ 北大 AI（114 人）运行，成功率 > 80%，输出文件字段完整

Step 2: 将抓取结果补充回 teachers.json
  - 产出物: 修改 `scrape_profiles` 输出逻辑，直接在 teacher_profiles 每项下新增 `homepage` 字段
  - 输出结构：
    ```json
    {
      "name": "刘家瑛",
      "profile_url": "...",
      "email": "liujiaying@pku.edu.cn",
      "interests": ["计算机视觉研究中心"],
      "title": "教授",
      "homepage": {
        "research_fields": ["智能媒体技术与视觉理解"],
        "bio": "刘家瑛，教授，IEEE Fellow...",
        "representative_works": "...",
        "personal_homepage": null,
        "recruiting_status": "unknown"
      }
    }
    ```
  - email 补全逻辑：列表页 email 为 null 且抓取到 email 时，用抓取值覆盖
  - 验收: 输出的 teachers.json 与原格式兼容（仅新增 homepage 字段），原字段不变

Step 3: 预筛评分增加 homepage 关键词匹配
  - 产出物: 修改 `src/teacher_list_prescreen.py` + `config/prescreen_scoring.json`
  - 在 scoring config 中新增 `interest_target_keywords` 字段（默认词池：NLP/LLM/CV/ML/深度学习/强化学习/数据挖掘/知识图谱/多模态/信息检索/推荐系统等）
  - 新增权重 `homepage_keyword_match_bonus`（每命中一个关键词 +3 分）和 `homepage_keyword_match_cap`（上限 15 分）
  - 匹配范围：`homepage.research_fields` + `homepage.bio` + `interests`（列表页已有）
  - 验收: 对北大 CS + AI 运行 prescreen，top 50 候选中研究方向匹配度显著高于随机

### 非目标
- 不写学校特定的 profile 页解析规则（全部用通用启发式）
- 不接入 LLM（后续独立任务）
- 不改动已有提取器（teacher_extractors/）
- 不改动 scholar 抓取链路
- 新增依赖需先确认

### 参考
- 现有 prescreen 机制: `src/teacher_list_prescreen.py`, `config/prescreen_scoring.json`
- 北大 CS profile 页示例: `https://cs.pku.edu.cn/info/1061/1602.htm`（边凯归）
- 北大 AI profile 页示例: `https://www.ai.pku.edu.cn/info/1312/1683.htm`（刘家瑛）
- 清华 AI profile 页示例: `https://collegeai.tsinghua.edu.cn/rydw/qzpi/dongyinpeng.htm`（董胤蓬）
- 上交 CS profile 页示例: `https://www.cs.sjtu.edu.cn/jiaoshiml/chenhaibo.html`（陈海波）

### 自动化验收命令
- 运行环境: .venv（项目已有虚拟环境）
- 执行命令格式: python src/xxx
- 正确工作流: collector（采集）→ scraper（补充 homepage）→ collector --prescreen-dir（预筛）

[Step1: 抓取北大教师主页详情]
```
python -c "
import sys; sys.path.insert(0, 'src')
from teacher_profile_scraper import scrape_profile
r = scrape_profile('https://cs.pku.edu.cn/info/1061/1602.htm')
assert r['research_fields'], f'research_fields empty: {r}'
assert r['bio'], f'bio empty: {r}'
assert r['title'], f'title empty: {r}'
assert r['full_text'], f'full_text empty: {r}'
print('OK:', {k: (v[:50] + '...' if isinstance(v, str) and len(v) > 50 else v) for k, v in r.items()})
"
```

[Step2: 批量抓取并写回 teachers.json]
```
python src/teacher_profile_scraper.py \
  --input output/teacher_pool/北京大学/计算机学院\ \&\ 王选计算机研究所/teachers.json \
  --output output/teacher_pool/北京大学/计算机学院\ \&\ 王选计算机研究所/teachers.json
python -c "
import json; d = json.loads(open('output/teacher_pool/北京大学/计算机学院 & 王选计算机研究所/teachers.json', encoding='utf-8').read())
has_homepage = sum(1 for p in d['teacher_profiles'] if p.get('homepage'))
has_title = sum(1 for p in d['teacher_profiles'] if p.get('title'))
has_full_text = sum(1 for p in d['teacher_profiles'] if (p.get('homepage') or {}).get('full_text'))
print(f'Total: {len(d[\"teacher_profiles\"])}, homepage: {has_homepage}, title: {has_title}, full_text: {has_full_text}')
assert has_homepage > 90, f'Success rate too low: {has_homepage}/120'
"
```

[Step3: prescreen 带关键词匹配（使用 --prescreen-dir 读磁盘）]
```
python src/teacher_list_collector.py --prescreen-dir output/teacher_pool --keywords "自然语言处理,大语言模型,计算机视觉,机器学习" --top-n 10
python -c "
import json; d = json.loads(open('output/teacher_pool/北京大学/人工智能研究院/prescreen.json', encoding='utf-8').read())
print(f'Top candidates: {len(d[\"top_candidates\"])}')
for c in d['top_candidates'][:5]:
    print(f'  {c[\"name\"]} score={c[\"score\"]} tier={c[\"tier\"]} kw={c[\"matched_keywords\"]}')
"
```

### 成功条件
- 所有步骤验收命令通过（exit code 0）
- 全部 16 个学院 1480 位教师抓取成功率 > 80%（实际 homepage 1329/1480 = 89.8%，0 失败）
- teachers.json 与原格式兼容（原字段不变，新增 homepage 字段，回填 email/title）
- full_text 中 nav 噪音明显减少（去重 + 关键词过滤 + 短行块过滤）
- prescreen --prescreen-dir 不重新采集，直接读磁盘做预筛
- prescreen 分数区分度显著（AI 从 2 种分数扩展到 7+ 种，tier A 候选数 > 50%）

### 各校抓取统计（2026-04-20）

| 学校 | 学院数 | 教师数 | homepage | email | title |
|------|--------|--------|----------|-------|-------|
| 北大 | 2 | 234 | 233(99.6%) | 115(49.1%) | 232(99.1%) |
| 清华 | 7 | 667 | 667(100%) | 387(58.0%) | 407(61.0%) |
| 上交 | 6 | 479 | 476(99.4%) | 473(98.7%) | 394(82.3%) |
| **合计** | **15** | **1480** | **1329(89.8%)** | **975(65.9%)** | **1033(69.8%)** |

备注：清华电子工程系(147人)无 profile_url（JS 渲染页面），未计入抓取范围。

### 错误处理约定
- 如某步失败：先分析原因，给出修复方案，等确认后再修
- 如连续两次失败：停下来，列出可能原因，不要继续盲目重试
- 如遇到环境/依赖问题：报告具体报错，不要自行修改环境配置
