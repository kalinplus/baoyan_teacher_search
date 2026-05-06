from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
:root {{
  --bg: #f5f7fa;
  --card-bg: #fff;
  --primary: #2563eb;
  --danger: #dc2626;
  --text: #1f2937;
  --text-secondary: #6b7280;
  --border: #e5e7eb;
  --radius: 12px;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}}
.container {{
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
}}
header {{
  margin-bottom: 24px;
}}
header h1 {{
  margin: 0 0 8px;
  font-size: 1.5rem;
}}
header .meta {{
  color: var(--text-secondary);
  font-size: 0.95rem;
}}
.toolbar {{
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 20px;
}}
.toolbar input[type="text"] {{
  flex: 1 1 260px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 0.95rem;
}}
.toolbar select {{
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 0.95rem;
  background: var(--card-bg);
}}
.count {{
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 12px;
}}
.card {{
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 20px;
  margin-bottom: 16px;
  transition: transform .15s ease, box-shadow .15s ease;
}}
.card:hover {{
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}}
.card-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}}
.card-header h2 {{
  margin: 0;
  font-size: 1.25rem;
}}
.score {{
  font-weight: 700;
  font-size: 1.1rem;
  color: var(--primary);
  white-space: nowrap;
}}
.section-title {{
  font-weight: 600;
  font-size: 0.9rem;
  margin: 14px 0 6px;
  color: var(--text);
}}
.reasons, .risks {{
  margin: 0;
  padding-left: 18px;
}}
.reasons li, .risks li {{
  margin-bottom: 6px;
  font-size: 0.95rem;
}}
.risks li {{
  color: var(--danger);
}}
.card.sent {{
  opacity: 0.6;
}}
.card.sent .card-header h2 {{
  text-decoration: line-through;
  color: var(--text-secondary);
}}
.sent-toggle {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}}
.sent-toggle input {{
  cursor: pointer;
}}
.empty {{
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}}
.back {{
  display: inline-block;
  margin-bottom: 16px;
  color: var(--primary);
  text-decoration: none;
  font-size: 0.9rem;
}}
.back:hover {{ text-decoration: underline; }}
.index-list {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.index-list li {{
  margin-bottom: 10px;
}}
.index-list a {{
  display: block;
  background: var(--card-bg);
  padding: 14px 18px;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  text-decoration: none;
  color: var(--text);
  transition: transform .15s ease, box-shadow .15s ease;
}}
.index-list a:hover {{
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}}
.index-list .item-title {{
  font-weight: 600;
  font-size: 1.05rem;
}}
.index-list .item-meta {{
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-top: 4px;
}}
</style>
</head>
<body>
<div class="container">
{body}
</div>
<script>
(function() {{
  const searchInput = document.getElementById('search');
  const sortSelect = document.getElementById('sort');
  const cards = Array.from(document.querySelectorAll('.card'));
  const countEl = document.getElementById('count');
  function update() {{
    const q = (searchInput ? searchInput.value : '').toLowerCase().trim();
    const sort = sortSelect ? sortSelect.value : 'score-desc';
    let visible = 0;
    cards.forEach(card => {{
      const text = card.textContent.toLowerCase();
      const show = !q || text.includes(q);
      card.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    if (countEl) countEl.textContent = '共 ' + visible + ' 条结果';
    const parent = document.getElementById('card-list');
    const shown = cards.filter(c => c.style.display !== 'none');
    shown.sort((a, b) => {{
      const sa = parseFloat(a.dataset.score || 0);
      const sb = parseFloat(b.dataset.score || 0);
      if (sort === 'score-desc') return sb - sa;
      if (sort === 'score-asc') return sa - sb;
      const na = (a.dataset.name || '').toLowerCase();
      const nb = (b.dataset.name || '').toLowerCase();
      return na.localeCompare(nb, 'zh-CN');
    }});
    shown.forEach(c => parent.appendChild(c));
  }}
  if (searchInput) searchInput.addEventListener('input', update);
  if (sortSelect) sortSelect.addEventListener('change', update);
  update();

  // Sent-status persistence
  (function() {{
    const storageKey = 'sent_emails_' + document.title.replace(/[^a-zA-Z0-9\\u4e00-\\u9fa5]/g, '_');
    let sentMap = {{}};
    try {{
      sentMap = JSON.parse(localStorage.getItem(storageKey) || '{{}}');
    }} catch(e) {{}}
    document.querySelectorAll('.sent-toggle input').forEach(function(cb) {{
      const teacher = cb.dataset.teacher;
      if (sentMap[teacher]) {{
        cb.checked = true;
        cb.closest('.card').classList.add('sent');
      }}
      cb.addEventListener('change', function() {{
        const card = this.closest('.card');
        if (this.checked) {{
          card.classList.add('sent');
          sentMap[teacher] = true;
        }} else {{
          card.classList.remove('sent');
          delete sentMap[teacher];
        }}
        localStorage.setItem(storageKey, JSON.stringify(sentMap));
      }});
    }});
  }})();
}})();
</script>
</body>
</html>
"""


def json_to_html(data: dict, title: str) -> str:
    school = data.get("school", "")
    college = data.get("college", "")
    recommendations = data.get("recommendations", [])

    header_html = f"""
<header>
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
    <h1>{school} · {college}</h1>
    <span class="score">共 {len(recommendations)} 位推荐老师</span>
  </div>
  <div class="meta">按匹配分数排序，可搜索关键词或按姓名/分数排序</div>
</header>
<div class="toolbar">
  <input type="text" id="search" placeholder="搜索老师姓名、研究方向、关键词...">
  <select id="sort">
    <option value="score-desc">分数从高到低</option>
    <option value="score-asc">分数从低到高</option>
    <option value="name">按姓名排序</option>
  </select>
</div>
<div class="count" id="count">共 {len(recommendations)} 条结果</div>
<div id="card-list">
"""

    cards_html = ""
    for rec in recommendations:
        teacher = rec.get("teacher", "未知")
        score = rec.get("match_score", 0)
        reasons = rec.get("match_reasons", [])
        risks = rec.get("risk_flags", [])

        reasons_html = "\n".join(f"<li>{r}</li>" for r in reasons)
        risks_html = "\n".join(f"<li>{r}</li>" for r in risks) if risks else "<li>暂无明确风险提示</li>"

        safe_teacher = teacher.replace('"', '&quot;')
        cards_html += f"""
<div class="card" data-score="{score}" data-name="{teacher}">
  <div class="card-header">
    <h2>{teacher}</h2>
    <div style="display:flex;align-items:center;gap:12px;">
      <span class="score">匹配分 {score}</span>
      <label class="sent-toggle">
        <input type="checkbox" data-teacher="{safe_teacher}">
        <span>已发送</span>
      </label>
    </div>
  </div>
  <div class="section-title">匹配理由</div>
  <ul class="reasons">
    {reasons_html}
  </ul>
  <div class="section-title">风险提示</div>
  <ul class="risks">
    {risks_html}
  </ul>
</div>
"""

    body = header_html + cards_html + "\n</div>\n"
    return HTML_TEMPLATE.format(title=title, body=body)


def build_index(groups: list[tuple[str, str, int]]) -> str:
    """groups: list of (name, relative_html_path, count)"""
    body = """
<header>
  <h1>推荐结果汇总</h1>
  <div class="meta">点击下方卡片查看各学院/机构的推荐详情</div>
</header>
<ul class="index-list">
"""
    for name, path, count in groups:
        body += f"""
<li>
  <a href="{path}">
    <div class="item-title">{name}</div>
    <div class="item-meta">共 {count} 位推荐老师</div>
  </a>
</li>
"""
    body += "\n</ul>\n"
    return HTML_TEMPLATE.format(title="推荐结果汇总", body=body)


def process_directory(input_dir: Path, out_dir: Path) -> tuple[str, int] | None:
    rec_file = input_dir / "recommendations.json"
    if not rec_file.exists():
        return None
    data = json.loads(rec_file.read_text(encoding="utf-8"))
    school = data.get("school", "")
    college = data.get("college", "")
    count = len(data.get("recommendations", []))
    name = f"{school} · {college}" if school and college else input_dir.name
    html = json_to_html(data, name)
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", name)
    out_path = out_dir / f"{safe_name}.html"
    out_path.write_text(html, encoding="utf-8")
    return name, out_path.name, count


def main():
    parser = argparse.ArgumentParser(description="Convert recommendations.json to HTML")
    parser.add_argument("--input", "-i", help="Single directory containing recommendations.json, or omit to scan output/")
    parser.add_argument("--output", "-o", default="html_report", help="Output directory for HTML files")
    args = parser.parse_args()

    repo_root = Path(__file__).parent
    out_dir = repo_root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.input:
        input_dirs = [Path(args.input)]
    else:
        output_dir = repo_root / "output"
        input_dirs = sorted({
            p.parent for p in output_dir.rglob("recommendations.json")
            if any(part in ("recommendations", "teacher_pool") for part in p.relative_to(output_dir).parts)
        })

    groups = []
    for d in input_dirs:
        result = process_directory(d, out_dir)
        if result:
            name, filename, count = result
            groups.append((name, filename, count))
            print(f"Generated: {out_dir / filename} ({count} teachers)")

    if len(groups) > 1:
        index_html = build_index(groups)
        index_path = out_dir / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        print(f"Generated index: {index_path}")

    if not groups:
        print("No recommendations.json found.")
        return

    print(f"\nAll files saved to: {out_dir}")
    if len(groups) > 1:
        print(f"Open in browser: file://{out_dir / 'index.html'}")
    else:
        print(f"Open in browser: file://{out_dir / groups[0][1]}")


if __name__ == "__main__":
    main()
