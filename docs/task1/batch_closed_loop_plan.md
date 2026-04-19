# 任务1后续方向：批量闭环缺失项与模块落地计划

## 背景
当前已完成离线预筛（prescreen）与单老师链路（author_id -> scholar）。

当前缺口是“批量闭环编排”尚未落地：
- 还没有从 prescreen Top N 自动批量推进到 author_id 和 scholar 的统一入口。
- 还没有同名老师候选二次校验，首候选策略会引入误匹配风险。
- 还没有最终推荐汇总输出（可解释理由 + 风险提示）。

## 目标
实现最小可运行批量闭环：
1. 输入 teachers.json + prescreen.json。
2. 自动读取 top_candidates 并批量执行 author_id 解析与 scholar 抓取。
3. 产出 final_recommendations.json，包含可解释推荐依据。

## 模块拆分（新增）

### 1) 批量编排入口
- 模块建议：src/batch_closed_loop.py
- 职责：
  - 读取 prescreen.json 的 top_candidates。
  - 顺序调用作者解析与 scholar 抓取模块。
  - 聚合结果并落盘 final_recommendations.json。
- 失败策略：fail fast，任一步骤抛错即中断并返回非 0。

### 2) 候选消歧模块
- 模块建议：src/author_disambiguation.py
- 职责：
  - 对 author_id 候选做姓名一致性和学校一致性校验。
  - 仅在校验通过时返回 author_id 并允许写入缓存。
- 说明：
  - 这是当前闭环正确性的核心缺口。
  - 不做“静默降级到首候选”的兜底。

### 3) Scholar 批处理执行层
- 模块建议：src/scholar_batch_runner.py
- 职责：
  - 对已消歧通过的 teacher 列表批量调用现有 ScholarAuthorClient。
  - 标准化采集结果与失败信息（teacher 维度）。

### 4) 推荐汇总模块
- 模块建议：src/recommendation_assembler.py
- 职责：
  - 合并 prescreen 分数、命中原因、scholar 指标。
  - 输出推荐结果与风险提示（例如：同名风险、信息缺失）。
- 输出文件：
  - output/{学校}/{学院}/final_recommendations.json

## 复用现有模块（不重写）
- src/teacher_list_prescreen.py：预筛结果输入源。
- src/author_id_resolver.py：author_id 获取主逻辑。
- src/scholar_client.py：Scholar 结构化抓取主逻辑。
- src/teacher_list_io.py：JSON 读写与输出目录风格保持一致。

## 输出契约（建议）
final_recommendations.json 顶层建议字段：
- school
- college
- generated_at
- total_candidates
- resolved_candidates
- failed_candidates
- recommendations

recommendations 单项建议字段：
- teacher
- prescreen_score
- prescreen_tier
- prescreen_reasons
- author_id
- author_id_source
- scholar_metrics
- recommendation_reason
- risk_flags

## 实施顺序
1. 先做 author_id 消歧模块，并替换首候选策略。
2. 再做批量编排入口（串起 prescreen -> author_id -> scholar）。
3. 最后做 recommendation 汇总与输出契约。

## 验收标准
- 输入同一份 prescreen.json，多次运行结果稳定。
- 发生同名冲突时不再默默落入错误老师，必须显式失败或跳过并记录原因。
- 生成 final_recommendations.json 且字段完整。
- 不新增第三方依赖。

## 验收命令（草案）
- conda run -n baoyan python src/batch_closed_loop.py --school 清华大学 --college 计算机科学与技术系 --pool-dir output/teacher_pool
- conda run -n baoyan python -m unittest tests.test_author_id_resolver tests.test_scholar_client tests.test_teacher_list_collector
