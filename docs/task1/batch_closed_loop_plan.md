# 任务1后续方向：批量闭环缺失项与模块落地计划

## 背景
当前已完成离线预筛（prescreen）与单老师链路（author_id -> scholar）。

当前缺口是“批量闭环编排”尚未落地：
- 还没有从 prescreen Top N 自动批量推进到 author_id 和 scholar 的统一入口。
- 还没有基于“首候选 author_id + 两层跳过校验”的防误匹配逻辑。
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
  - 保留“首个匹配 author_id”策略，不做多候选回退。
  - 对首个候选执行两层校验：
    1) author_id 反查冲突校验：
       使用已存在缓存反查该 author_id；若已绑定到其他老师姓名，则标记当前老师为 skip。
    2) Scholar 主页姓名校验：
       若第1层无冲突，则抓取该 author_id 对应 Scholar 主页；若主页姓名与当前检索老师姓名不一致，则标记为 skip。
  - 仅在两层校验都通过时，才允许将该 author_id 作为有效结果写入缓存并继续后续流程。
- 说明：
  - 该策略用于处理“部分老师没有 Scholar 主页”导致的误命中问题。
  - 跳过是显式状态，不做静默兜底。

### 2.1) 跳过原因约定
- `author_id_conflict_existing_teacher`：该 author_id 在历史缓存中已绑定其他老师。
- `scholar_name_mismatch`：该 author_id 的 Scholar 主页姓名与当前检索老师不一致。

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
1. 先打通单老师闭环（优先做 2/3/4）：
  - 保留首候选策略，执行两层跳过校验（已在 author_id_resolver 落地）。
  - 在单老师入口补齐 recommendation 输出与失败明细（含 skip reason）。
  - 目标是先验证“单老师可稳定跑通”。
2. 单老师闭环通过后，再做批量编排入口（实现 1）：
  - 读取 prescreen top_candidates。
  - 批量调用单老师闭环能力并汇总成功/失败。
3. 最后做 recommendation 汇总增强：
  - 完整落盘 final_recommendations.json 契约。
  - 细化 recommendation_reason 与 risk_flags 规则。

## 验收标准
- 输入同一份 prescreen.json，多次运行结果稳定。
- 首候选命中后必须执行两层校验；任一层不通过均显式跳过并记录 skip reason。
- 两层都通过时才写 author_id 缓存，避免错误缓存污染。
- 先满足单老师闭环可用（成功路径 + skip 路径都可复现），再进入批量编排开发。
- 生成 final_recommendations.json 且字段完整。
- 不新增第三方依赖。

## 验收命令（草案）
- 单老师闭环（先验收）：
- conda run -n baoyan python src/scholar_client.py --school 清华 --teacher 夏树涛 --out-dir output
- conda run -n baoyan python src/batch_closed_loop.py --school 清华大学 --college 计算机科学与技术系 --pool-dir output/teacher_pool
- conda run -n baoyan python -m unittest tests.test_author_id_resolver tests.test_scholar_client tests.test_teacher_list_collector
