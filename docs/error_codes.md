# 错误码文档

## 目的
为显式抛错点和关键透传异常提供统一编码，便于日志检索与问题归类。

## 模块前缀

| 前缀 | 模块 |
|---|---|
| AID | `author_id_resolver.py` |
| ADI | `author_disambiguation.py` |
| SCH | `scholar_client.py` |
| BCL | `batch_closed_loop.py` |
| TLC | `teacher_list_core.py` |
| TIO | `teacher_list_io.py` |
| PSR | `teacher_list_prescreen.py` |
| THU | `teacher_extractors/thu.py` |
| SJT | `teacher_extractors/sjtu.py` |
| TCOL | `teacher_list_collector.py` |
| UTL | `utils.py` |

## 核心错误码示例

| 错误码 | 描述 |
|---|---|
| AID-007 | 学校别名无法归一化 |
| AID-010 | Google 搜索结果未解析到 author_id |
| AID-011 | author_id 与缓存中的其他老师冲突 |
| AID-015 | Scholar 主页姓名与检索老师不一致 |
| BCL-001 ~ BCL-008 | 批量闭环输入校验失败 |
| PSR-003 ~ PSR-009 | 预筛打分配置非法 |
| NET-001 ~ NET-006 | 外部网络/请求/JSON 解析异常（透传） |

## 业务跳过状态

| 错误码 | skip_reason | 描述 |
|---|---|---|
| SKIP-001 | `author_id_conflict_existing_teacher` | author_id 已绑定其他老师 |
| SKIP-002 | `scholar_name_mismatch` | Scholar 主页姓名与当前老师不一致 |

## 维护说明
- 新增显式抛错时，同步更新本文档并分配新错误码。
- 修改已有错误消息模板时，不复用旧错误码。
- 当前仅完成映射文档，运行时日志尚未统一输出 `error_code` 字段（待实施）。
