# 保研导师信息工具 — Scholar 数据获取方案

## 总体分工

整个 Scholar 数据获取分为两个阶段，两个服务各司其职：

**阶段一：定位 author_id**（用 ScraperAPI 通用代理 + Google Search）
**阶段二：拉取详细学术数据**（用 SerpApi `google_scholar_author` 引擎）

这样做的原因是：SerpApi 免费额度仅 100 次/月，而 ScraperAPI 免费额度 5000 次，且 Google Search 页面的解析逻辑简单、稳定，不需要 SerpApi 的结构化能力。

---

## 阶段一：通过 ScraperAPI + Google Search 获取 author_id

### 原理

构造如下 Google 搜索查询：

```
site:scholar.google.com "老师姓名" "学校英文名"
```

Google 搜索结果中会出现该老师的 Scholar Profile 页面链接，格式为：

```
https://scholar.google.com/citations?user=XXXXXXX&hl=en
```

其中 `XXXXXXX` 即为 `author_id`。

### 代码实现

```python
import requests
from bs4 import BeautifulSoup
import re

SCRAPER_API_KEY = "YOUR_SCRAPERAPI_KEY"

def get_author_id(name: str, school_en: str) -> str | None:
    """
    通过 Google Search 搜索 Scholar Profile，提取 author_id。
    name: 老师姓名（中文或拼音均可）
    school_en: 学校英文名（从对照表中取）
    """
    query = f'site:scholar.google.com "{name}" "{school_en}"'
    payload = {
        "api_key": SCRAPER_API_KEY,
        "url": f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=en",
        "render": "false",  # Google Search 无需 JS 渲染
        "country_code": "us",
    }
    resp = requests.get("https://api.scraperapi.com/", params=payload, timeout=60)
    soup = BeautifulSoup(resp.text, "html.parser")

    # 提取所有 href 中包含 scholar.google.com/citations?user= 的链接
    for a in soup.find_all("a", href=True):
        href = a["href"]
        match = re.search(r"scholar\.google\.com/citations\?user=([A-Za-z0-9_-]+)", href)
        if match:
            return match.group(1)

    return None
```

### 注意事项

- 若第一次搜索未命中（老师没有 Scholar 主页，或姓名歧义），可以尝试用拼音全名或加上研究方向关键词再搜一次。
- 结果应做**本地缓存**（见下文），避免重复消耗配额。
- ScraperAPI 对 Google Search 计 1 credit/次，5000 次免费额度对于保研工具的使用量完全够用。

---

### 文档参考

**ScraperAPI：**
- 通用代理端点（用于抓 Google Search）：<https://docs.scraperapi.com/synchronous-apis/using-the-api-endpoint>
- Google Search 结构化端点（参考）：<https://docs.scraperapi.com/structured-data-endpoints/search-and-insights/google/google-serp-api>
- 结构化端点总览：<https://docs.scraperapi.com/structured-data-endpoints>


## 阶段二：通过 SerpApi 拉取 Scholar 详细数据

### 可获取的字段

使用 `google_scholar_author` 引擎，输入 `author_id` 后可获得：

| 字段 | 说明 |
|---|---|
| `name` / `affiliations` | 姓名、机构 |
| `email` | 邮箱（如公开） |
| `interests` | 研究兴趣标签 |
| `cited_by.table` | 总引用数、h-index、i10-index |
| `cited_by.graph` | 按年引用量（可算近3/5年） |
| `articles` | 所有论文列表（标题、年份、引用数、合著者） |

### 代码实现

```python
from serpapi import GoogleSearch

SERPAPI_KEY = "YOUR_SERPAPI_KEY"

def get_scholar_data(author_id: str) -> dict:
    """拉取作者完整 Scholar 数据"""
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_scholar_author",
        "author_id": author_id,
        "hl": "en",
        "sort": "pubdate",  # 按发表时间排序，方便提取近年论文
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    author_info = results.get("author", {})
    cited_by = results.get("cited_by", {})
    articles = results.get("articles", [])

    return {
        "name": author_info.get("name"),
        "affiliations": author_info.get("affiliations"),
        "email": author_info.get("email"),
        "interests": [i["title"] for i in author_info.get("interests", [])],
        "cited_by_total": cited_by.get("table", [{}])[0].get("citations", {}).get("all"),
        "h_index": cited_by.get("table", [{}])[1].get("h_index", {}).get("all"),
        "i10_index": cited_by.get("table", [{}])[2].get("i10_index", {}).get("all"),
        "cited_by_graph": cited_by.get("graph", []),  # 按年数据
        "articles": articles,
    }
```

若论文数量超过一页（默认返回约20篇），需要翻页：

```python
def get_all_articles(author_id: str) -> list:
    all_articles = []
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_scholar_author",
        "author_id": author_id,
        "hl": "en",
        "sort": "pubdate",
        "num": "100",
    }
    search = GoogleSearch(params)
    while True:
        results = search.get_dict()
        all_articles.extend(results.get("articles", []))
        if "next" not in results.get("serpapi_pagination", {}):
            break
        search.params_dict["start"] = results["serpapi_pagination"]["next_start"]
    return all_articles
```

---

### 文档参考

**SerpApi：**
- Google Scholar 主文档：<https://serpapi.com/google-scholar-api>
- Google Scholar Author 引擎：<https://serpapi.com/google-scholar-author-api>

## 本地缓存机制

author_id 一旦确认基本不变，详细数据也只需定期更新，因此缓存非常重要。推荐用 SQLite 或简单的 JSON 文件：

```python
import json
import os

CACHE_FILE = "author_id_cache.json"

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_author_id_cached(name: str, school_en: str) -> str | None:
    cache = load_cache()
    key = f"{school_en}::{name}"
    if key in cache:
        return cache[key]
    author_id = get_author_id(name, school_en)
    if author_id:
        cache[key] = author_id
        save_cache(cache)
    return author_id
```

---

## 完整调用流程

```
输入：学校名称（中/英/缩写） + 老师姓名
    ↓
学校名称对照表 → 取英文全称
    ↓
查本地缓存（author_id_cache.json）
    ├─ 命中 → 直接进入阶段二
    └─ 未命中 → 阶段一：ScraperAPI + Google Search → 写入缓存
    ↓
阶段二：SerpApi google_scholar_author → 拉取详细数据
    ↓
结构化输出（命令行摘要 + 写入 {out_dir}/{学校}/{老师姓名}/）
```

---

## 配额消耗估算

| 操作 | 服务 | 消耗 |
|---|---|---|
| 搜索 author_id（首次） | ScraperAPI | 1 credit/人 |
| 拉取作者详情 | SerpApi | 1 次/人 |
| 翻页拉取全部论文 | SerpApi | 1 次/页 |
| 重复查询同一老师 | 均不消耗（缓存） | 0 |