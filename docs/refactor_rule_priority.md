**状态：已完成（2026-04-29）**

### 背景
`teacher_list_core.py` 中的 `collect_teachers` 目前固定先执行 auto-extractor，再通过 `should_use_fallback` 与人工规则做质量分比较。这套机制在清华自动化系 `bdmd.htm` 场景中产生了反效果：auto-extractor 因为页面所有文本都包在 `<a>` 标签里而虚高质量分（0.529），人工规则（68 条纯净教师记录）反而因为质量分略低（0.5）被忽略，最终输出混入导航垃圾。

### 最终目标
有匹配规则时直接采用规则结果，无匹配时才回退到 auto-extractor；删除基于质量分的仲裁逻辑。

### 分步计划（有序，每步独立可验收）

Step 1: 修改 `collect_teachers` 为规则优先
  - 产出物: `src/teacher_list_core.py`
  - 验收: `collect_teachers` 在有匹配 rule 时，直接执行 `collect_profiles_with_rule`，跳过 `should_use_fallback` 比较；仅在无匹配 rule 时才走 auto-extractor

Step 2: 清理 `should_use_fallback` 与 `profile_quality`
  - 产出物: `src/teacher_list_helpers.py`
  - 验收: 删除 `should_use_fallback` 函数、`profile_quality` 函数，以及 `teacher_list_core.py` 中对其的 import；确认没有其他引用方

Step 3: 回归验证已有适配学院
  - 产出物: 运行日志
  - 验收: 重新运行已有规则的学院（如清华计算机系、清华软件学院、北大人工智能研究院等），确认 `teachers.json` 仍正常产出，无异常

### 非目标
- 不动任何 `teacher_extractors/*.py` 中的规则实现
- 不动 `source_urls.json`
- 不改 `clean_teacher_profiles`、`extract_teacher_profiles_auto` 等辅助函数
- 不新增依赖

### 参考
- `src/teacher_list_core.py:82-96`
- `src/teacher_list_helpers.py:430-457`

### 自动化验收命令
- 运行环境: conda 环境 `baoyan`
- 执行命令格式: `PYTHONPATH=src conda run -n baoyan python src/...`

[Step1 验收:]
```bash
PYTHONPATH=src conda run -n baoyan python -c "
from teacher_list_core import collect_teachers
from teacher_extractors import get_rules
from teacher_list_models import SourceRecord
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
record = SourceRecord(school='清华大学', college='自动化系', url='https://www.au.tsinghua.edu.cn/zsjy/bdmd.htm')
result = collect_teachers(record, timeout=30, rules=get_rules(), logger=logger)
print('mode:', result.get('mode', 'unknown'))
print('count:', len(result['teachers']))
print('first 5:', result['teachers'][:5])
"
```
预期输出：`mode` 为 `fallback:thu_au_bdmd_h4s1`，`first 5` 中无导航垃圾项（如"紫冬视频"）。

[Step2 验收:]
```bash
grep -r "should_use_fallback\|profile_quality" src/ || echo "clean"
```
预期输出：`clean`

[Step3 验收:]
```bash
PYTHONPATH=src conda run -n baoyan python src/teacher_list_collector.py --school 清华大学 --college 计算机科学与技术系 --out-dir output/teacher_pool
PYTHONPATH=src conda run -n baoyan python src/teacher_list_collector.py --school 北京大学 --college 人工智能研究院 --out-dir output/teacher_pool
```
预期输出：两条均正常完成，mode 为对应 fallback 规则名。

### 成功条件
- Step1 验收命令输出 mode 为 `fallback:thu_au_bdmd_h4s1`，且无导航垃圾项
- Step2 验收命令输出 `clean`
- Step3 至少两个已有学院的 collector 正常完成，输出与改动前一致

### 错误处理约定
- 如 Step1 验收失败：检查 `collect_teachers` 中 rule 匹配和分支逻辑
- 如 Step2 清理时发现其他引用方：先列出引用位置，确认安全后再删除
- 如 Step3 回归失败：对比改动前后 `teachers.json` diff，定位影响范围
