我来仔细分析这几个页面的内容，归纳字段设计。

四个基础层页面已读完，再看扩展层的四个个人主页。

8 个页面全部读完。现在来做系统性归纳。

---

## Q2 决策：LLM 提取 Schema 设计

基于对 4 个基础层页面（北大李戈、清华吕凯风、浙大沈春华、上交崔少波）和 4 个扩展层个人主页的实际内容分析，以下是字段设计建议。

---

### **观察：各类页面实际能提供什么**

先把原始素材摊开看清楚，再决定字段。

**基础层（学校个人主页）的实际内容差异极大：**

| 字段 | 北大李戈（`cs.pku.edu.cn`） | 清华吕凯风（`iiis.tsinghua.edu.cn`） | 浙大沈春华（`person.zju.edu.cn`） | 上交崔少波（`soai.sjtu.edu.cn`） |
|---|---|---|---|---|
| 姓名 | ✅（仅姓名，页面内容为空） | ✅ | ✅ | ✅ |
| 职称 | ❌（页面抓取失败/空） | ✅ 助理教授 | ✅ 求是讲席教授/博士生导师 | ✅ 助理教授 |
| email | ❌ | ❌（字段存在但值为空） | ✅ chunhuashen@zju.edu.cn | ✅ shaobo.cui@sjtu.edu.cn |
| homepage_url | ❌ | ✅ https://kaifeng.ac/ | ✅（有"个人主页"链接） | ✅ https://shaobo.info/ |
| 研究方向（关键词） | ❌ | ✅ 机器学习理论、AI安全与对齐、优化 | ✅ 机器学习、计算机视觉 | ✅ 因果智能、世界模型、LLM、AI医疗 |
| 个人简介（bio） | ❌ | ✅（一段话） | ✅（极简，指向个人主页） | ✅（一段话） |
| 学生列表 | ❌ | ✅（PhD/Master/Alumni） | ❌ | ❌ |
| 课程 | ❌ | ✅（两门课） | ❌ | ❌ |
| Google Scholar | ❌ | ✅ | ❌ | ❌ |
| GitHub | ❌ | ✅ | ❌ | ❌ |

**结论**：北大的学校主页页面实际上是空的（李戈那条 URL 只有导航菜单，内容区为空），说明**基础层字段必须设计成全部可选/nullable，不能假设一定能抓到**。清华 IIIS 的页面是最丰富的，浙大和上交居中，北大最差。

**扩展层（个人主页）的实际内容：**

| 字段 | 李戈（`ligechina.github.io`） | 吕凯风（`kaifeng.ac`） | 沈春华（`cshen.github.io`） | 崔少波（`shaobo.info`） |
|---|---|---|---|---|
| 研究方向（详细） | ✅ Program Language Processing, NLP, SE | ✅ ML Theory, AI Safety, Optimization（含三段详细描述） | ✅ CV, LLM, Embodied AI | ✅ 四个方向（含 LLMs for Science 等） |
| 招生状态 | ❌（无明确表述） | ✅（隐含：有 incoming PhD） | ✅（明确：Hiring postdocs/RA，长期有效） | ✅（有 For Prospective Students 段落） |
| 招生要求 | ❌ | ❌（指向中文版） | ❌（指向 PDF） | ✅（有描述） |
| 近期代表作（recent_works） | ✅（大量，含年份/会议/引用数） | ✅（含 Oral/Outstanding Paper 标注） | ❌（主页未列论文，仅 news） | ✅（Selected Publications） |
| Lab 名称 | ❌ | ❌ | ❌ | ✅ DeepDelta Lab (Δ Lab) |
| 学生列表 | ❌ | ✅（PhD/Master/Alumni，含去向） | ✅（博士/硕士/已毕业，含去向） | ❌ |
| 课程 | ❌（有 Teaching 标签页但未展开） | ✅（两门，含评分） | ❌ | ❌ |
| 荣誉/奖项 | ✅（Distinguished Paper Awards） | ✅（ICLR 2025 Outstanding Paper） | ✅（Pattern Recognition Best Paper） | ✅（G-Research PhD Prize、NAACL Outstanding） |
| 学术服务（conference_roles） | ❌ | ✅（Area Chair, Reviewer） | ❌ | ❌ |
| 开源项目/软件 | ❌ | ✅（UOJ） | ✅（FCOS, SOLO 等） | ✅（3 个 PyPI 包） |

---

### **Schema 设计建议**

基于以上分析，设计原则是：**字段命名语义清晰、全部 nullable、LLM 提取时不强求填满**。

#### **基础层（Step2 从学校主页提取）**

```json
{
  "name": "李戈",
  "school": "北京大学",
  "college": "计算机学院",
  "profile_url": "https://cs.pku.edu.cn/info/1071/1679.htm",

  "title": "教授",
  "email": "lige@pku.edu.cn",
  "homepage_url": "https://ligechina.github.io/",
  "google_scholar_url": null,
  "github_url": null,

  "research_keywords": ["程序语言处理", "自然语言处理", "软件工程"],
  "bio": "北京大学计算机学院长聘教授，研究方向为机器学习在程序语言处理、NLP和软件工程中的应用。",

  "is_phd_supervisor": true,
  "is_master_supervisor": true,
  "supervisor_type": ["博导", "硕导"],

  "data_source": "school_profile",
  "extracted_at": "2026-04-21T23:18:41"
}
```

字段说明：

- `title`：职称，如"教授"、"副教授"、"助理教授"、"研究员"、"百人计划研究员"等，**不统一成英文**，保留原始表述
- `email`：学校邮箱优先，个人主页邮箱备用
- `homepage_url`：触发 Step3 的关键字段，null 则跳过 Step3
- `google_scholar_url`、`github_url`：部分学校主页（如 IIIS）会直接列出，顺手提取，不强求
- `research_keywords`：3\~8 个，从页面上列出的研究方向关键词直接提取，**不要 LLM 自行生成**
- `bio`：一段话，从页面"个人简介"字段提取，若页面无内容则 null，**不要 LLM 自行编造**
- `is_phd_supervisor`、`is_master_supervisor`、`supervisor_type`：对保研最关键的字段，很多学校主页直接标注"博士生导师/硕士生导师"，应优先提取

#### **扩展层（Step3 从个人主页提取）**

```json
{
  "homepage_url": "https://ligechina.github.io/",

  "research_summary": "李戈教授的研究聚焦于将概率方法应用于机器学习，主要涵盖程序语言处理（代码生成、代码补全、代码摘要）、自然语言处理和软件工程三个方向，近年来重点关注 LLM 在代码领域的应用，包括 CodeDPO、aiXcoder、FAN 等工作。",

  "recruiting_status": "active",
  "recruiting_targets": ["phd", "master", "postdoc"],
  "recruiting_note": "长期招收博士生，欢迎联系",

  "recent_works": [
    {
      "title": "FAN: Fourier Analysis Networks",
      "venue": "NeurIPS 2025",
      "year": 2025,
      "citation_count": 40
    },
    {
      "title": "Self-collaboration Code Generation via ChatGPT",
      "venue": "TOSEM 2024",
      "year": 2024,
      "citation_count": 463
    }
  ],

  "lab_name": "DeepDelta Lab",
  "lab_url": null,

  "students_phd_count": 5,
  "students_master_count": 1,
  "students_note": "含 incoming 学生",

  "awards": ["ICLR 2025 Outstanding Paper Award", "ACM SIGSOFT Distinguished Paper Award (×3)"],

  "conference_roles": ["NeurIPS 2025 Area Chair", "ICLR 2026 Area Chair"],

  "courses_teaching": ["从头训练大语言模型：理论与实践", "计算机与人工智能应用数学"],

  "open_source_projects": ["FCOS (anchor-free object detector, included in PyTorch)", "causal-strength (PyPI)"],

  "data_source": "personal_homepage",
  "extracted_at": "2026-04-21T23:18:41"
}
```

字段说明：

- `research_summary`：这是**需要 LLM 主动总结**的字段（而非直接提取），基于个人主页全文综合归纳，2\~4 句话，突出研究主线和近年方向
- `recruiting_status`：枚举值 `"active"` / `"unknown"` / `"not_recruiting"`，从 News / 主页文字中判断；沈春华明确写了"Hiring"，崔少波有"For Prospective Students"段落，吕凯风有 incoming 学生，李戈无明确信息
- `recruiting_targets`：从 `["phd", "master", "postdoc", "intern", "ra"]` 中选，根据页面描述填写
- `recruiting_note`：原文摘录或简短总结，如"Hiring multiple postdocs/RA in LLMs, multimodal, embodied AI"
- `recent_works`：取最近 3\~5 篇代表作，**不要全量**；优先选高引用或 Oral/Best Paper；`citation_count` 从页面"Cited by N"提取，无则 null
- `students_phd_count` / `students_master_count`：从学生列表数出来，`students_note` 补充说明（如"含 incoming"）
- `awards`：从主页 News / Bio / 论文标注中提取荣誉
- `conference_roles`：Area Chair / PC Chair 等，对判断学术地位有参考价值
- `open_source_projects`：有则填，对判断工程影响力有用

---

### **几个设计决策说明**

**关于 `bio` vs `research_summary` 的分工**：`bio` 在基础层，是从学校主页直接摘抄的原文简介（通常 1\~2 句），不做加工；`research_summary` 在扩展层，是 LLM 读完整个个人主页之后综合归纳的，信息量更大、更有针对性。两者不重复。

**关于 `recent_works` 的粒度**：不需要全量论文列表（李戈的主页有上百篇，全提取没有意义），只要 3\~5 篇能代表当前研究方向的即可，LLM 选取时优先选近 2 年 + 高引用 + 顶会。

**关于 `recruiting_status` 的判断**：这是保研场景下最有价值的字段之一。四个样本里，沈春华是最明确的（直接写了"Hiring"），崔少波次之，吕凯风需要从"has incoming students"推断，李戈完全没有信息。LLM 应该保守判断，无明确信息时输出 `"unknown"` 而非猜测。

**关于 `supervisor_type` 和 `is_phd_supervisor`**：这两个字段在基础层就要提取，因为学校主页通常会标注"博士生导师"，而个人主页反而不一定写。对于保研场景，这是筛选导师的硬条件。

### 具体实施
写好合适的 prompt, 让 LLM 直接按格式生成 json，字段就为上述示例所示，内容根据页面提取