#!/usr/bin/env bash
# run_task0_1.sh - 一键完成任务0（教师池采集）+ 任务1（离线预筛）
# Usage: 修改下方 CONFIG 区域的变量后执行 ./run_task0_1.sh

set -euo pipefail

# ==============================================================================
# CONFIG 区域 —— 按需修改以下变量
# ==============================================================================

# 目标学校（必须与 docs/task0/source_urls.json 中的 school 字段一致）
# 可选示例: 清华大学 / 北京大学 / 上海交通大学 / 浙江大学
SCHOOL="清华大学"

# 目标学院（必须与 docs/task0/source_urls.json 中的 college 字段一致）
# 可选示例:
#   清华大学: 计算机科学与技术系 / 软件学院 / 人工智能学院 / 交叉信息研究院
#             网络科学与网络空间研究院 / 自动化系 / 电子工程系
#             深圳国际研究生院（计算机科学与技术方向）
#   北京大学: 人工智能研究院 / 计算机学院 & 王选计算机研究所
#   上海交通大学: 人工智能学院 / 计算机学院（网络空间安全学院、密码学院）
#                 浦江国际学院（原密西根学院） / 溥渊未来技术学院
COLLEGE="计算机科学与技术系"

# 你的研究兴趣关键词（逗号分隔，用于预筛评分加权）
KEYWORDS="NLP,大语言模型,机器学习"

# 预筛参数
TOP_N=20          # 选取 top N 候选人
BUDGET=20         # 最终预算上限（不超过 top_n）

# 输出目录
OUT_DIR="output/teacher_pool"

# 环境变量文件（需包含 SERPAPI_KEY 等；如已 export 可忽略）
ENV_FILE=".env"

# 是否强制重新采集（true=每次都重新抓；false=若已有 teachers.json 则跳过采集直接预筛）
FORCE_COLLECT=false

# ==============================================================================
# 以下逻辑通常无需修改
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载环境变量
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
    echo "[INFO] Loaded env from $ENV_FILE"
fi

TEACHERS_JSON="$OUT_DIR/$SCHOOL/$COLLEGE/teachers.json"

if [[ "$FORCE_COLLECT" == "false" && -f "$TEACHERS_JSON" ]]; then
    echo "[INFO] Found existing $TEACHERS_JSON, skipping collection."
    echo "[INFO] Running prescreen only ..."
    python src/teacher_list_collector.py \
        --prescreen-dir "$OUT_DIR/$SCHOOL/$COLLEGE" \
        --top-n "$TOP_N" \
        --budget "$BUDGET" \
        --keywords "$KEYWORDS"
else
    echo "[INFO] Collecting teachers for $SCHOOL / $COLLEGE ..."
    python src/teacher_list_collector.py \
        --school "$SCHOOL" \
        --college "$COLLEGE" \
        --prescreen \
        --out-dir "$OUT_DIR" \
        --top-n "$TOP_N" \
        --budget "$BUDGET" \
        --keywords "$KEYWORDS"
fi

echo ""
echo "[DONE] Results:"
echo "  - teachers.json      => $TEACHERS_JSON"
if [[ -f "$OUT_DIR/$SCHOOL/$COLLEGE/prescreen.json" ]]; then
    echo "  - prescreen.json     => $OUT_DIR/$SCHOOL/$COLLEGE/prescreen.json"
    CANDIDATES=$(python -c "import json,sys; d=json.load(open('$OUT_DIR/$SCHOOL/$COLLEGE/prescreen.json')); print(len(d.get('top_candidates',[])))" 2>/dev/null || echo "?")
    echo "  - top_candidates     => $CANDIDATES 人"
fi
