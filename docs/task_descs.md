## 总体描述
一个 CLI 工具，甚至初步就是一个脚本作为入口就行。
输入，我希望就是学校+姓名，输出，则是其基本信息、学术相关的结构化信息、以及可能的推荐程度等等。

## 任务1：获取结构化信息 
- 根据老师的“学校+姓名“，使用 SCRAPERAPI_KEY 搜索，获取其 google scholar author id
- 根据 author id，使用 SERPAPI_KEY 的接口，获取老师的结构化信息

可能的注意点：
- 两个 API Key 用量不足。一般不会出现，至少我会想办法付费的
- 本地缓存，这个有必要实现。只缓存 author id 就行，避免重复查询
- 当前已实现获取 google scholar author id 的独立模块：src/author_id_resolver.py（AuthorIdResolver）。
- 当前主流程已接入：src/scholar_client.py 中可直接使用学校+姓名自动发现 author id，并交给 ScholarAuthorClient 获取结构化信息。
- 当前查询策略已收敛为单次查询：`site:scholar.google.com/citations + 学校英文缩写 + 用户输入的老师名`。
- 用户输入老师名若包含中文会给 warning（提示准确性风险），但仍按用户输入继续查询。
- `pypinyin` 暂不引入，作为可选增强项后续评估（新增依赖前需审批）。
- 当前支持通过 `--log-level DEBUG` 输出 author_id 解析全链路日志（入参、缓存命中/未命中、查询词、请求页、正则命中、最终写缓存）。
- 发文相关统计基于当前 author 结果页抓取窗口；输出 `publications_truncated` 标记是否可能存在分页截断。
- 结构化信息的具体字段，好像被删了，查看"output/南京大学/周志华"目录下的结果作为参考，然后写到文档里吧

参考 API 文档：

**ScraperAPI：**
- 通用代理端点（用于抓 Google Search）：<https://docs.scraperapi.com/synchronous-apis/using-the-api-endpoint>
- Google Search 结构化端点（参考）：<https://docs.scraperapi.com/structured-data-endpoints/search-and-insights/google/google-serp-api>
- 结构化端点总览：<https://docs.scraperapi.com/structured-data-endpoints>

**SerpApi：**
- Google Scholar 主文档：<https://serpapi.com/google-scholar-api>
- Google Scholar Author 引擎：<https://serpapi.com/google-scholar-author-api>


## 任务2：获取基本信息
基本信息，比如学校、学院、邮箱、研究兴趣（可能 google scholar 里也有），这些是基本的。
还有一些进阶的，比如近期 selected paper, 实验室成员和去向，项目，主页的额外通知、要求。当然首先要先找到主页。

找主页，有两个基本想法：
1. SCRAPERAPI_KEY 直接搜索，看返回结果。根据我用搜索引擎的经验，学校主页和个人主页都是有可能出来的，可能都要看，毕竟有的老师弄前者，有的后者，有的干脆没有后者，比较千人千面
2. google scholar 上很多老师会放主页链接？不知道能不能一起爬下来，也不知道是不是所有老师都放，要确认

TODO（下一步）
- 支持从输入文件读取多位老师名单，按记录批量执行抓取流程（学校归一化 -> author_id 解析 -> 结构化信息输出）。
- 输入文件形式暂不固定，后续讨论（候选：txt/csv/json）。
- 批量模式先复用现有单老师输出契约与目录结构，避免引入额外字段变更。

## 任务3：匹配度分析
有两个层级：
1. 你写一些你的期望方向，用关键词、同义词、近义词匹配之类的方法（直接你多写一点就行，简化实现），匹配老师的研究兴趣，缺点是精度可能不高。以及可以用一些院校、引用量之类的，做一些筛选

2. 传一份 md 简历，让 LLM 帮你匹配。prompt 要设计一下

## 任务4：CLI 甚至 GUI 包装
...