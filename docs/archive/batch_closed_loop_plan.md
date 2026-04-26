# 批量闭环计划（已落地归档）

## 目标
实现最小可运行批量闭环：输入 `teachers.json + prescreen.json`，自动读取 `top_candidates` 批量执行 author_id 解析与 Scholar 抓取，产出 `final_recommendations.json`。

## 输出契约

`final_recommendations.json` 顶层字段：
- `school`、`college`、`generated_at`
- `total_candidates`、`resolved_candidates`、`failed_candidates`
- `failed_candidate_details`（含 `skip_reason`，如 `author_id_conflict_existing_teacher`、`scholar_name_mismatch`）
- `recommendations`

`recommendations` 单项字段：
- `teacher`、`prescreen_score`、`prescreen_tier`、`prescreen_reasons`
- `author_id`、`author_id_source`、`scholar_metrics`
- `recommendation_reason`、`risk_flags`

## 实施状态

1. 单老师闭环：已完成（两层 skip 校验、recommendation 输出、失败明细）。
2. 批量编排入口：已完成（`src/batch_closed_loop.py`，老师级容错继续执行）。
3. 重试与失败增强：已完成（外部请求 2 次重试 + 递增超时）。

## 下一步
- 细化 `recommendation_reason` 与 `risk_flags` 规则颗粒度。
- 补充端到端真实样本冒烟与回归验证。

## 验收标准
- 同一 `prescreen.json` 多次运行结果稳定。
- 首候选命中后必须执行两层校验；任一层不通过均显式跳过并记录 `skip_reason`。
- 单老师异常不阻塞整批；最终落盘 `final_recommendations.json` 字段完整。
- 不新增第三方依赖。
