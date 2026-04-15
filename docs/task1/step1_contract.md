# 任务1文档：任务1数据契约与边界

## 背景
当前系统已具备显式 author_id 查询结构化信息能力（src/scholar_client.py），并已实现“学校+老师姓名 -> 自动发现 author_id”（src/author_id_resolver.py）。

Step1 的目标是先固定契约与边界，避免后续实现阶段返工。

## 模块边界
- 模块A（待实现）：AuthorIdResolver
- 职责: 根据 school + teacher 定位并返回 author_id
- 输入: school, teacher
- 输出: author_id 及来源信息（可选）

- 模块B（已存在）：ScholarAuthorClient
- 职责: 根据 author_id 拉取结构化信息
- 输入: author_id
- 输出: 标准化结构化字段

## 输入契约
### AuthorIdResolver 输入
- school: string，必填
- teacher: string，必填
- timeout: int，可选，默认30

约束:
- school 必须能被 config/universities.json 归一化；否则抛 ValueError。
- teacher 去首尾空白后不能为空；否则抛 ValueError。

### ScholarAuthorClient 输入
- author_id: string，必填，不能为空

## 输出契约
### AuthorIdResolver 输出（最小）
- author_id: string
- source: string（建议值: google_search）
- matched_school: string（归一化后的学校名）
- matched_teacher: string

### 最终 result.json 输出（沿用现有字段）
- author_id
- name
- affiliations
- email
- interests
- citations_all
- citations_last_1y
- citations_last_3y
- citations_last_5y
- publications_total
- publications_last_1y
- publications_last_3y
- publications_last_5y
- h_index_all
- i10_index_all
- source
- matched_school
- matched_teacher

## 缓存契约（仅针对 author_id）
- 缓存对象: school + teacher -> author_id
- 缓存命中: 直接返回 author_id，不发起搜索请求
- 缓存落盘: 仅在成功解析 author_id 后写入
- 缓存未命中: 发起搜索并解析

## 错误处理约定（遵循 AGENT.md）
- Fail fast，不做静默降级。
- 业务层不吞异常，错误向上抛出。
- 常见错误类型:
  - ValueError: 输入非法（学校无法归一化、teacher为空）
  - RuntimeError: 搜索结果无可用 author_id
  - requests.HTTPError: 外部接口返回非2xx
  - TimeoutError/requests 超时异常: 外部请求超时

## 非目标
- 不实现主页抓取与基本信息深挖。
- 不实现匹配度分析。
- 不新增依赖（需审批后才可变更 requirements）。

## Step1 验收
- 文档可独立回答以下问题:
  - 输入字段是什么，非法输入如何处理
  - 输出字段是什么
  - 缓存何时读写
  - 异常如何处理

- 验收命令:
  - conda run -n baoyan python -c "print('step1-contract-reviewed')"
