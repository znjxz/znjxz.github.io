#!/usr/bin/env python3
"""生成首页：扫描已构建的 notes/*.html，从各自的 <title> 和描述生成索引。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES = ROOT / "notes"

INDEX = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>znjxz · 笔记花园</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Noto+Serif+SC:wght@300;400;500&display=swap">
<style>
  :root {{
    --paper:#faf8f5; --ink:#1f1d1a; --ink-soft:#3d3934; --muted:#8a8279;
    --gold:#8c7554; --rule:#ddd6cb; --rule-soft:#ece7df;
  }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --paper:#1a1917; --ink:#e8e3da; --ink-soft:#c9c3b8;
            --muted:#8f877c; --gold:#c9a97a; --rule:#33302b; --rule-soft:#272521; }}
  }}
  *,*::before,*::after{{box-sizing:border-box}}
  body{{
    margin:0;background:var(--paper);color:var(--ink);
    font-family:"EB Garamond","Noto Serif SC",Georgia,"Songti SC","SimSun",serif;
    font-size:18.5px;line-height:1.85;
    font-feature-settings:"palt" 1,"kern" 1,"liga" 1;
    -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
  }}
  body::before{{
    content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.36;
    background-image:
      radial-gradient(circle at 18% 24%,rgba(140,117,84,.035) 0 1px,transparent 1px),
      radial-gradient(circle at 72% 68%,rgba(140,117,84,.028) 0 1px,transparent 1px);
    background-size:137px 149px,211px 197px;
  }}
  .wrap{{position:relative;z-index:1;max-width:40rem;margin:0 auto;padding:5.5rem 1.75rem 7rem}}
  header{{margin-bottom:1rem}}
  .eyebrow{{font-size:.72rem;letter-spacing:.28em;text-transform:uppercase;
           color:var(--gold);margin:0 0 1.5rem;font-weight:500}}
  h1{{font-size:2.15rem;font-weight:400;line-height:1.25;letter-spacing:.015em;
      margin:0 0 .85rem}}
  h1 em{{font-style:italic;color:var(--ink-soft)}}
  .sub{{color:var(--muted);font-size:1rem;line-height:1.7;margin:0;max-width:30rem}}
  .rule-double{{margin:2.75rem 0 0;border:0;border-top:1px solid var(--rule);
                border-bottom:1px solid var(--rule-soft);height:3px}}
  h2{{font-size:.74rem;font-weight:500;letter-spacing:.22em;text-transform:uppercase;
     color:var(--muted);margin:4rem 0 1.75rem;padding-bottom:.85rem;
     border-bottom:1px solid var(--rule-soft)}}
  ul{{list-style:none;padding:0;margin:0}}
  li+li{{border-top:1px solid var(--rule-soft)}}
  li a{{display:block;padding:1.35rem .5rem 1.35rem 0;color:inherit;text-decoration:none;
        transition:padding-left .25s ease}}
  li a:hover{{padding-left:.55rem}}
  li a:hover .t{{color:var(--gold)}}
  .t{{display:block;font-size:1.15rem;font-weight:500;line-height:1.5;
      transition:color .25s ease}}
  .d{{display:block;color:var(--muted);font-size:.95rem;line-height:1.65;margin-top:.4rem}}
  .note{{margin-top:1rem;padding:1.9rem 0 0 1.6rem;border-left:1px solid var(--gold);
         font-size:1rem;line-height:1.95;color:var(--ink-soft)}}
  .note em{{color:var(--muted);font-style:italic}}
  footer{{margin-top:5.5rem;padding-top:1.9rem;border-top:1px solid var(--rule);
          color:var(--muted);font-size:.82rem;letter-spacing:.05em}}
  footer p{{margin:0}}
  footer .sep{{color:var(--rule);margin:0 .7rem}}
  @media (max-width:520px){{
    body{{font-size:17.5px}}
    .wrap{{padding:3.5rem 1.3rem 5rem}}
    h1{{font-size:1.8rem}}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">Notes</p>
    <h1>znjxz · <em>笔记花园</em></h1>
    <p class="sub">这些笔记还在生长。会改写、会增补，也会删掉当初觉得对的部分。</p>
    <hr class="rule-double">
  </header>
{entries}
  <h2>关于这里</h2>
  <div class="note">
    这不是博客。<br>
    博客按日期发布，写完就不再变动；<br>
    这里按主题互相牵连，并且<em>永远没有最终版本</em>。
  </div>
  <footer>
    <p>© <span id="y"></span> znjxz<span class="sep">·</span>持续更新<span class="sep">·</span>非终稿</p>
  </footer>
</div>
<script>document.getElementById('y').textContent=new Date().getFullYear();</script>
</body>
</html>
"""


def read_note(f):
    t = f.read_text(encoding="utf-8", errors="ignore")
    title = re.search(r"<h1>(.*?)</h1>", t, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', t, re.S)
    return (
        re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else f.stem,
        (desc.group(1).strip() if desc else ""),
    )


def main():
    if not NOTES.is_dir():
        sys.exit("没有 notes/ 目录，先运行 build_site.py")
    items = []
    for f in sorted(NOTES.glob("*.html")):
        title, desc = read_note(f)
        items.append((title, desc, f.name))

    if not items:
        entries = '  <h2>笔记</h2>\n  <ul><li><a href="#"><span class="t">暂无</span></a></li></ul>'
    else:
        lis = []
        for title, desc, fn in items:
            d = f'<span class="d">{desc}</span>' if desc else ""
            lis.append(f'    <li><a href="/notes/{fn}"><span class="t">{title}</span>{d}</a></li>')
        entries = '  <h2>笔记</h2>\n  <ul>\n' + "\n".join(lis) + "\n  </ul>"

    (ROOT / "index.html").write_text(INDEX.format(entries=entries), encoding="utf-8")
    print(f"首页已生成，收录 {len(items)} 篇")


if __name__ == "__main__":
    main()
