> 说明：本文件用于"规则补充与回归样例"记录，不是任务0执行的前置输入。
> 已验证时间：2026-04-22（本地网络）
> 验证方式：逐页检查 HTTP 状态码、最终 URL、title、页面长度、关键词与姓名样本命中。

```md
学校：浙江大学
学院：软件学院
URL：http://www.cst.zju.edu.cn/szdw/list.htm
分页类型：无（单页全量）
人名区域：姓名在 `a` 标签的 `title` 属性与文本中，链接指向 `https://person.zju.edu.cn/{教师ID}`，如 `<a href="https://person.zju.edu.cn/chenc" target="_blank" title="陈纯">陈纯</a>`
姓名样本：陈纯、黄铭钧、尹建伟、高云君、伍赛、宋明黎、张旭鸿、潘家雨、张微、贝毅君
限制：
- 原域名 `https://cst.zju.edu.cn` 会触发 SSL EOF 错误，需使用 `http://www.cst.zju.edu.cn`；
- 页面需要携带 User-Agent 请求头，否则返回 403；
- 教师个人主页使用 `person.zju.edu.cn`，该域名有 FRMS 反爬指纹，部分页面返回"该教师个人中文主页暂未开放"；
- scraper 抓取 person.zju.edu.cn 时 full_text 可能为空（页面被 JS 重定向或暂未开放），但不影响名单采集
验证结果：通过（HTTP 200；fallback:zju_cst_person 规则稳定抽取 98 位教师；全部含 person.zju.edu.cn 主页链接）
```

---

```md
学校：浙江大学
学院：计算机科学与技术学院
URL：http://www.cs.zju.edu.cn/csen/27003/list.htm
分页类型：无（单页全量）
人名区域：同一模板，姓名在 `a` 标签的 `title` 属性与文本中，链接指向 `https://person.zju.edu.cn/{教师ID}`；页面按研究所分组列出（人工智能研究所、计算机软件研究所、计算机系统研究所、数字媒体与网络技术研究所、计算机图形学研究所等）
姓名样本：陈超超、范鹤鹤、黄忠东、黄正行、况琨、刘泽民、李纪为、林兰芬、钱沄涛、唐敏、童若锋、王文冠、翁恺、翁彦琳、杨易、朱强、朱霖潮
限制：
- 原域名 `https://cs.zju.edu.cn` 返回 404，需使用 `http://www.cs.zju.edu.cn`；
- 页面需要携带 User-Agent 请求头，否则返回 403；
- 教师个人主页同样使用 `person.zju.edu.cn`，存在 FRMS 反爬和部分页面"暂未开放"问题；
- 部分教师（如陈纯）同时出现在计算机学院和软件学院名单中，跨学院去重时需注意
验证结果：通过（HTTP 200；fallback:zju_cs_person 规则稳定抽取 73 位教师；全部含 person.zju.edu.cn 主页链接）
```

---

**⚠️ 补充说明：**
- `person.zju.edu.cn` 为浙江大学统一的教师个人主页平台，采用 FRMS 指纹防护，直接 curl/requests 抓取时部分页面会被 JS 重定向到"暂未开放"提示页；
- scraper 模块已配置 User-Agent 和重试策略，对 person.zju.edu.cn 的抓取成功率约为 97%（浙软 97/98，浙计 73/73）；
- 采集链路中 Step1（名单采集）与 Step2（详情页抓取）解耦，即使个人主页抓取失败也不影响教师名单的完整性；
- 如需补充未在学院列表页出现的教师（如部分使用 `mypage.zju.edu.cn` 域名的教师），需查找其他列表入口或手动补充。
