# 错误码文档

## 目的
为当前仓库的显式抛错点和关键透传异常提供统一错误码，便于日志检索、告警聚合和问题定位。

## 规则
- 错误码格式：`<模块前缀>-<三位序号>`。
- 同一错误码对应一个稳定的触发语义。
- `skip_reason` 属于业务跳过状态，不等同于程序失败，但一并纳入编码。

## 实施状态（重要）
- 当前仅完成“错误码文档映射”，尚未把错误码系统实施到既有代码。
- 也就是说，创建本文档之前就已存在的抛错点，当前仍然是原始异常与原始消息，不会自动附带 `error_code` 字段。
- 本文档中的错误码用于人工对照与问题归类，不代表运行时日志/异常对象已经统一输出这些编码。

## author_id_resolver.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| AID-001 | FileNotFoundError | University mapping not found: {config_path} | 学校别名配置文件不存在。 |
| AID-002 | FileNotFoundError | Compound surnames config not found: {config_path} | 复姓配置文件不存在。 |
| AID-003 | ValueError | Compound surnames config must be a JSON array: {config_path} | 复姓配置文件结构非法（应为数组）。 |
| AID-004 | ValueError | Compound surname must be a string: {item!r} | 复姓配置项类型非法（应为字符串）。 |
| AID-005 | ValueError | Compound surname cannot be empty | 复姓配置项为空字符串。 |
| AID-006 | ValueError | Compound surnames config is empty: {config_path} | 复姓配置为空数组。 |
| AID-007 | ValueError | Unknown school alias: {raw_school} | 学校别名无法归一化。 |
| AID-008 | RuntimeError | Missing environment variable: SCRAPERAPI_KEY | 缺少 `SCRAPERAPI_KEY` 环境变量。 |
| AID-009 | ValueError | Teacher name cannot be empty | 老师姓名为空。 |
| AID-010 | RuntimeError | No author_id found from Google Search results | Google 搜索结果中未解析到 author_id。 |
| AID-011 | RuntimeError | skip_reason=author_id_conflict_existing_teacher ... | author_id 与缓存中的其他老师冲突。 |
| AID-012 | RuntimeError | Cannot extract Scholar profile name for author_id={author_id} | 无法从 Scholar 主页提取姓名。 |
| AID-013 | RuntimeError | Scholar profile name is empty for author_id={author_id} | Scholar 主页姓名提取后为空。 |
| AID-014 | RuntimeError | Scholar profile name is invalid for author_id={author_id} | Scholar 主页姓名标准化后无效。 |
| AID-015 | RuntimeError | skip_reason=scholar_name_mismatch ... | Scholar 主页姓名与检索老师不一致。 |
| AID-016 | ValueError | Cannot build pinyin query for teacher name: {teacher_name} | 中文姓名无法转为拼音检索词。 |
| AID-017 | ValueError | No uppercase ASCII school abbreviation found for school: {school} | 学校别名中无可用英文缩写。 |

## author_disambiguation.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| ADI-001 | re-raise | raise | 对非 skip 的 RuntimeError 不吞掉，继续向上抛出。 |

## scholar_client.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| SCH-001 | RuntimeError | Missing environment variable: SERPAPI_KEY | 缺少 `SERPAPI_KEY` 环境变量。 |
| SCH-002 | RuntimeError | SerpApi error: {payload['error']} | SerpApi 返回业务错误。 |
| SCH-003 | FileNotFoundError | University mapping not found: {config_path} | 学校映射配置文件不存在。 |
| SCH-004 | ValueError | Unknown school alias: {raw_school} | 学校别名无法归一化。 |

## batch_closed_loop.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| BCL-001 | FileNotFoundError | Input file not found: {path} | 批处理输入文件不存在（teachers/prescreen）。 |
| BCL-002 | ValueError | Input file must be a JSON object: {path} | 输入文件顶层结构不是 JSON 对象。 |
| BCL-003 | ValueError | teachers.json missing teacher_profiles array | teachers.json 缺少 `teacher_profiles`。 |
| BCL-004 | ValueError | teachers.json teacher_profiles has no valid names | teachers.json 中无有效教师姓名。 |
| BCL-005 | ValueError | prescreen.json missing top_candidates array | prescreen.json 缺少 `top_candidates`。 |
| BCL-006 | ValueError | top_candidates[{index}] must be an object | top_candidates 项结构非法。 |
| BCL-007 | ValueError | top_candidates[{index}].name is required | top_candidates 项缺少 name。 |
| BCL-008 | ValueError | top_candidates[{index}].name not found in teachers.json: {teacher_name} | 候选老师不在教师池名单中。 |

## teacher_list_core.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| TLC-001 | RuntimeError | No teachers extracted for {record.school} / {record.college} | 页面解析后没有有效教师。 |
| TLC-002 | RuntimeError | Duplicate names detected after cleaning for {record.school} / {record.college} | 清洗后出现重名冲突。 |

## teacher_list_io.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| TIO-001 | FileNotFoundError | Input source file not found: {path} | source_urls 输入文件不存在。 |
| TIO-002 | ValueError | Input source file must be a JSON array | source_urls 顶层结构非法。 |
| TIO-003 | ValueError | Source record at index {index} must be an object | 来源记录项不是对象。 |
| TIO-004 | ValueError | Source record at index {index} missing required fields | 来源记录缺失 school/college/url。 |
| TIO-005 | ValueError | Direct mode requires non-empty --school --college --url | 直连模式参数缺失。 |
| TIO-006 | ValueError | No source record matched --school/--college filters | 过滤条件未命中任何来源记录。 |

## teacher_list_prescreen.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| PSR-001 | ValueError | Prescreen scoring config field '{key}' must be a string array | 打分配置字段应为字符串数组。 |
| PSR-002 | ValueError | Prescreen scoring config field '{key}' must be a non-negative integer | 打分配置字段应为非负整数。 |
| PSR-003 | FileNotFoundError | Prescreen scoring config not found: {path} | 打分配置文件不存在。 |
| PSR-004 | ValueError | Prescreen scoring config must be a JSON object | 打分配置顶层结构非法。 |
| PSR-005 | ValueError | Prescreen scoring config field 'title_keywords' must be an object | `title_keywords` 结构非法。 |
| PSR-006 | ValueError | Prescreen scoring config field 'weights' must be an object | `weights` 结构非法。 |
| PSR-007 | ValueError | Prescreen scoring config field 'thresholds' must be an object | `thresholds` 结构非法。 |
| PSR-008 | ValueError | Prescreen scoring config thresholds must satisfy score_min <= score_max | 分数上下界配置非法。 |
| PSR-009 | ValueError | Prescreen scoring config thresholds must satisfy tier_b_min <= tier_a_min | 分层阈值配置非法。 |
| PSR-010 | FileNotFoundError | Contacted teachers file not found: {path} | 已联系名单文件不存在。 |
| PSR-011 | ValueError | Contacted teachers file must be a JSON object | 已联系名单顶层结构非法。 |
| PSR-012 | ValueError | Contacted teachers file missing 'schools' array | 已联系名单缺少 schools 数组。 |
| PSR-013 | ValueError | Contacted schools[{index}] must be an object | schools 项结构非法。 |
| PSR-014 | ValueError | Contacted schools[{index}].school is required | schools 项缺少 school 字段。 |
| PSR-015 | ValueError | Contacted schools[{index}].entries must be an array | entries 字段结构非法。 |
| PSR-016 | ValueError | Contacted schools[{index}].entries[{entry_index}] must be an object | entries 项结构非法。 |
| PSR-017 | ValueError | Contacted schools[{index}].entries[{entry_index}].name is required | entries 项缺少 name。 |
| PSR-018 | ValueError | teacher_profiles[{index}] must be an object | teacher_profiles 项结构非法。 |
| PSR-019 | ValueError | teacher_profiles[{index}].name is required | teacher_profiles 项缺少 name。 |
| PSR-020 | ValueError | teacher_profiles[{index}].interests must be an array | teacher_profiles.interests 结构非法。 |
| PSR-021 | ValueError | top_n must be > 0 | top_n 参数非法。 |
| PSR-022 | ValueError | budget must be > 0 | budget 参数非法。 |
| PSR-023 | ValueError | Prescreen payload missing school/college/url | prescreen 输入缺少学校/学院/URL。 |
| PSR-024 | ValueError | Prescreen payload missing teacher_profiles array | prescreen 输入缺少 teacher_profiles。 |

## teacher_extractors/thu.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| THU-001 | FileNotFoundError | SIGS subject keywords config not found: {THU_SIGS_SUBJECT_KEYWORDS_PATH} | SIGS 学科关键词配置文件不存在。 |
| THU-002 | ValueError | SIGS subject keywords config must be a JSON array | SIGS 学科关键词配置结构非法。 |
| THU-003 | ValueError | SIGS subject keyword must be string, got: {item!r} | SIGS 学科关键词项类型非法。 |
| THU-004 | ValueError | SIGS subject keyword cannot be empty | SIGS 学科关键词项为空。 |
| THU-005 | ValueError | SIGS subject keywords config cannot be empty | SIGS 学科关键词配置为空。 |
| THU-006 | ValueError | Anchor not found: {anchor_name} | 页面锚点不存在。 |
| THU-007 | ValueError | Invalid anchor order: {start_anchor} -> {end_anchor} | 页面锚点顺序非法。 |
| THU-008 | ValueError | Start keyword not found: {start_keyword} | 起始关键词不存在。 |
| THU-009 | ValueError | End keyword not found: {end_keyword} | 结束关键词不存在。 |
| THU-010 | ValueError | Invalid keyword order: {start_keyword} -> {end_keyword} | 关键词区间顺序非法。 |

## teacher_extractors/sjtu.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| SJT-001 | RuntimeError | SJTU CS AJAX content is not a string | SJTU 计算机学院 AJAX 返回 content 字段类型非法。 |

## teacher_list_collector.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| TCOL-001 | re-raise | raise | 在不允许部分导出的场景下，采集异常会被直接上抛。 |

## utils.py

| 错误码 | 异常类型 | 原始消息模板 | 描述 |
|---|---|---|---|
| UTL-001 | ValueError | Unsupported log level: {level} | 日志级别参数非法。 |

## 业务跳过状态（非异常）

| 错误码 | 字段 | 值 | 描述 |
|---|---|---|---|
| SKIP-001 | skip_reason | author_id_conflict_existing_teacher | author_id 与历史缓存老师冲突，当前老师被跳过。 |
| SKIP-002 | skip_reason | scholar_name_mismatch | Scholar 主页姓名与当前老师不一致，被跳过。 |

## 透传异常（外部依赖/网络层）

以下异常当前未做业务层吞噬，会按 fail-fast 原则直接透传：

| 错误码 | 异常类型 | 典型来源 | 描述 |
|---|---|---|---|
| NET-001 | requests.exceptions.HTTPError | `response.raise_for_status()` | 外部接口返回非 2xx。 |
| NET-002 | requests.exceptions.Timeout | `requests.get/post(..., timeout=...)` | 外部请求超时。 |
| NET-003 | requests.exceptions.ConnectionError | requests 连接阶段 | 网络连接异常。 |
| NET-004 | requests.exceptions.ChunkedEncodingError | requests 流式读取响应 | 分块响应中断（你在冒烟测试中遇到过）。 |
| NET-005 | requests.exceptions.RequestException | requests 基类异常 | 其他未细分的请求层错误。 |
| NET-006 | json.JSONDecodeError | `json.loads(...)` / `response.json()` | JSON 解析失败（输入文件或外部返回格式异常）。 |

## 维护说明
- 新增显式抛错时，必须同步更新本文档并分配新错误码。
- 修改已有错误消息模板时，不复用旧错误码，新增版本号后缀或新码。
- 推荐在日志中同时打印 `error_code` 与原始异常，便于检索。
