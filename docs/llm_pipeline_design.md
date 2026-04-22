# LLM Pipeline 设计讨论

## 整体流程

```
Step1 教师列表采集（已有，基本不改）
  ├── 自定义规则爬各学院师资页
  └── 输出: teachers.json [name, profile_url, school_page_title, ...]

Step2 学校个人主页抓取 + LLM 信息提取（替换现有的规则提取）
  ├── 抓 profile_url 页面 → 清洗文本
  ├── LLM 提取结构化信息: email, homepage_url, research_summary, ...
  └── 输出: enriched teachers.json

Step3 个人主页二次抓取（新增，如果 Step2 发现了 homepage_url）
  ├── 抓 homepage_url 页面 → 清洗文本
  ├── LLM 再次提取，字段更丰富: recruiting_status, recent_works, lab_info, ...
  └── 输出: 进一步 enriched teachers.json

Step4 LLM 匹配推荐（替换现有的规则评分 + Scholar 指标）
  ├── 输入: 教师信息 + 你的简历/论文/偏好
  └── 输出: 匹配度评估 + 推荐理由
```

## 待确认事项

请在每个问题下方写上你的决定。

### Q1: Scraper 框架

当前 `teacher_profile_scraper.py` 用 `requests + regex`，对固定站点足够。引入 Scrapy/Playwright 会增重很多，收益有限。

**你的决定:**

选项: A. 保持现状 requests+regex

---

### Q2: LLM 提取的输出 schema

建议分层设计：

**基础层**（Step2 提取）: `email`, `title`, `homepage_url`, `research_summary`（一段话）, `keywords`（3-8 个）, `bio`（一段话）

**扩展层**（Step3 提取，有 homepage 才有）: `recruiting_status`, `recruiting_requirements`, `recent_works`, `lab_members_count`, `courses_teaching`, `conference_roles`

**你的决定:**

选项: B. 两层一起做

如果选 B 或 C，请列出你想要的完整字段列表: 参考 docs/llm_generate_attributes.md 文档



---

### Q3: LLM 选型与成本

估算：~1500 教师 × 2 页面 × ~5k tokens ≈ 15M input tokens。

用 Claude Haiku 约 $15，Sonnet 约 $150。匹配阶段预筛到 top 100-200 后再做，成本可控。

**你的决定:**

选项: C. 其他。使用 deepseek-ai/DeepSeek-V3.2，硅基流动 API

---

### Q4: 批处理策略

- **A. 全量提取再匹配**：先批量跑完所有教师的 LLM 提取，存到磁盘，再统一做匹配。可复用、可审查中间结果。
- **B. 增量流式**：一边提取一边筛选，减少后续调用。

**你的决定:**

选项: 先实现 A

---

### Q5: Step4 匹配的输入

打算给 LLM 什么信息来判断匹配度？

- [✅] 简历全文
- [ ] 读过的论文列表（标题 + 摘要）
- [✅] 感兴趣的具体方向（自己写一段）
- [ ] 其他: __________

**补充说明:**

读过的论文不好放，暂时不考虑

注意提示词要严格一些，宁缺毋滥，找到最匹配的

---

### Q6: Google Scholar 数据

- **A. 完全不用 Scholar**：纯靠 LLM 读教师主页信息判断。
- **B. 作为补充输入**：能拿到 Scholar 数据的额外附带，拿不到不阻塞。

**你的决定:**

选项: A

---

### Q7: 其他想法或补充

<!-- 在这里写 -->
