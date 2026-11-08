#!/usr/bin/env python3
"""把 Obsidian 笔记（Markdown）构建成静态网页。

设计原则：
- 只有 frontmatter 里 publish: true 的笔记才会被构建（默认全部不公开）
- 双链 [[xxx]] 转成站内链接；指向不存在/未发布的笔记降级为纯文本
- 同一个模板，所有笔记共享老钱风版式

用法:
  build_site.py --vault "/data/thtf/Obsidian/Obsidian Vault" --out /tmp/pagesite
  build_site.py --vault ... --out ... --dry-run   # 只看会构建哪些
"""
import argparse
import html
import os
import re
import shutil
import sys
from pathlib import Path

try:
    import markdown
    import yaml
except ImportError:
    sys.exit("需要 markdown 和 pyyaml：pip install markdown pyyaml")

SKIP_DIRS = {".obsidian", ".smart-env", ".infio_json_db", ".git", ".trash", "backups"}


# ─────────────────────────── frontmatter ───────────────────────────
def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, text[m.end():]


def is_published(meta):
    v = meta.get("publish")
    return v is True or (isinstance(v, str) and v.strip().lower() in ("true", "yes", "1"))


# ─────────────────────────── wikilink ───────────────────────────
WL = re.compile(r"(!?)\[\[([^\]]+)\]\]")


def parse_wikilink(raw):
    """[[目标#标题|显示]] -> (目标, 锚点, 显示)"""
    parts = raw.split("|", 1)
    target = parts[0].strip()
    display = parts[1].strip() if len(parts) > 1 else None
    anchor = ""
    if "#" in target:
        target, anchor = target.split("#", 1)
        target, anchor = target.strip(), anchor.strip()
    return target, anchor, display


def convert_wikilinks(text, published_map, current_slug):
    """把 wikilink 换成 HTML 链接；未发布的降级为纯文本。"""
    def repl(m):
        embed, raw = m.group(1), m.group(2)
        target, anchor, display = parse_wikilink(raw)
        name = target or os.path.basename(current_slug)
        key = os.path.splitext(os.path.basename(name))[0]
        label = html.escape(display or (target or name))
        if embed:
            # 嵌入：目前不支持，降级为文字说明
            return f'<span class="embed-missing">〔嵌入：{label}〕</span>'
        slug = published_map.get(key)
        if not slug:
            return f'<span class="wikilink-unpublished">{label}</span>'
        href = f"/notes/{slug}.html"
        if anchor:
            href += "#" + anchor.replace(" ", "-")
        return f'<a class="wikilink" href="{href}">{label}</a>'
    return WL.sub(repl, text)


# ─────────────────────────── 模板 ───────────────────────────
TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · znjxz</title>
<meta name="description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Noto+Serif+SC:wght@300;400;500&display=swap">
<style>
  :root {{
    --paper:#faf8f5; --paper-deep:#f3efe9; --ink:#1f1d1a; --ink-soft:#3d3934;
    --muted:#8a8279; --gold:#8c7554; --rule:#ddd6cb; --rule-soft:#ece7df;
  }}
  @media (prefers-color-scheme:dark) {{
    :root {{ --paper:#1a1917; --paper-deep:#211f1c; --ink:#e8e3da; --ink-soft:#c9c3b8;
            --muted:#8f877c; --gold:#c9a97a; --rule:#33302b; --rule-soft:#272521; }}
  }}
  *,*::before,*::after{{box-sizing:border-box}}
  html{{-webkit-text-size-adjust:100%}}
  body{{
    margin:0;background:var(--paper);color:var(--ink);
    font-family:"EB Garamond","Noto Serif SC",Georgia,"Songti SC","SimSun",serif;
    font-size:18.5px;line-height:1.9;
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
  .wrap{{position:relative;z-index:1;max-width:40rem;margin:0 auto;padding:4.5rem 1.75rem 7rem}}
  .back{{display:inline-block;font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;
        color:var(--muted);text-decoration:none;margin-bottom:2.5rem;transition:color .2s}}
  .back:hover{{color:var(--gold)}}
  .eyebrow{{font-size:.72rem;letter-spacing:.28em;text-transform:uppercase;
           color:var(--gold);margin:0 0 1.4rem;font-weight:500}}
  h1{{font-size:2rem;font-weight:400;line-height:1.4;letter-spacing:.015em;margin:0 0 1.1rem}}
  .meta{{color:var(--muted);font-size:.88rem;letter-spacing:.04em;margin:0 0 2.6rem}}
  .rule-double{{margin:0 0 3.2rem;border:0;border-top:1px solid var(--rule);
               border-bottom:1px solid var(--rule-soft);height:3px}}
  article h2{{font-size:.74rem;font-weight:500;letter-spacing:.22em;text-transform:uppercase;
     color:var(--muted);margin:3.4rem 0 1.4rem;padding-bottom:.7rem;
     border-bottom:1px solid var(--rule-soft)}}
  article h3{{font-size:1.08rem;font-weight:500;margin:2.4rem 0 1rem;color:var(--ink-soft)}}
  article p{{margin:0 0 1.5rem}}
  article em{{font-style:italic;color:var(--ink-soft)}}
  article strong{{font-weight:500;color:var(--ink)}}
  article a{{color:var(--ink);text-decoration:none;
             border-bottom:1px solid var(--rule);transition:color .2s,border-color .2s}}
  article a:hover{{color:var(--gold);border-color:var(--gold)}}
  article ul,article ol{{margin:0 0 1.5rem;padding-left:1.4rem}}
  article li{{margin:0 0 .5rem}}
  article blockquote{{margin:2rem 0;padding:.4rem 0 .4rem 1.6rem;
             border-left:1px solid var(--gold);color:var(--ink-soft);font-size:1rem;
             font-style:normal}}
  article blockquote p:last-child{{margin-bottom:0}}
  article code{{font-family:"SF Mono","Cascadia Code",monospace;font-size:.88em;
                background:var(--paper-deep);padding:.1em .35em;border-radius:3px}}
  article pre{{background:var(--paper-deep);padding:1.1rem 1.3rem;border-radius:4px;
               overflow-x:auto;margin:1.8rem 0;line-height:1.65}}
  article pre code{{background:none;padding:0;font-size:.85em}}
  article img{{max-width:100%;height:auto;border-radius:4px;margin:1.5rem 0}}
  article hr{{border:0;border-top:1px solid var(--rule-soft);margin:3rem 0}}
  article table{{width:100%;border-collapse:collapse;margin:2rem 0;font-size:.94rem}}
  article th,article td{{text-align:left;padding:.75rem .6rem;
                         border-bottom:1px solid var(--rule-soft);vertical-align:top}}
  article th{{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;
              color:var(--muted);font-weight:500;border-bottom:1px solid var(--rule)}}
  .wikilink{{border-bottom:1px solid var(--gold)}}
  .wikilink-unpublished{{color:var(--muted);border-bottom:1px dotted var(--rule)}}
  .embed-missing{{color:var(--muted);font-size:.9em}}
  .tags{{margin:3.5rem 0 0;padding-top:1.6rem;border-top:1px solid var(--rule-soft)}}
  .tags span{{display:inline-block;font-size:.76rem;letter-spacing:.1em;
              color:var(--muted);margin:0 .8rem .5rem 0}}
  .tags span::before{{content:"#"}}
  footer{{margin-top:4rem;padding-top:1.8rem;border-top:1px solid var(--rule);
          color:var(--muted);font-size:.82rem;letter-spacing:.05em}}
  footer p{{margin:0 0 .5rem}}
  footer a{{color:var(--muted);text-decoration:none;border-bottom:1px solid var(--rule)}}
  footer a:hover{{color:var(--gold)}}
  @media (max-width:520px){{
    body{{font-size:17.5px}}
    .wrap{{padding:3rem 1.3rem 5rem}}
    h1{{font-size:1.62rem}}
    article table{{font-size:.86rem}}
  }}
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="/">← 花园</a>
  <p class="eyebrow">{eyebrow}</p>
  <h1>{title}</h1>
  <p class="meta">{meta_line}</p>
  <hr class="rule-double">
  <article>
{body}
  </article>
{tags_block}
  <footer>
    <p>这篇笔记仍在修订。<a href="/">返回花园</a></p>
    <p>© <span id="y"></span> znjxz</p>
  </footer>
</div>
<script>document.getElementById('y').textContent=new Date().getFullYear();</script>
</body>
</html>
"""


def strip_private_sections(body):
    """去掉不想公开的段落。

    规则：用 <!-- private:start --> / <!-- private:end --> 包裹的内容会被移除，
    以及标题为「## 结论」「## 消化」这类内部整理标记的整节。
    """
    body = re.sub(r"<!--\s*private:start\s*-->.*?<!--\s*private:end\s*-->", "",
                  body, flags=re.S)
    # 去掉「## 结论」到下一个同级标题（或文末）的整节
    body = re.sub(r"^##\s*(结论|消化|内部|TODO)\s*$.*?(?=^##\s|\Z)", "",
                  body, flags=re.S | re.M)
    return body


def render(md_text, meta, published_map, slug):
    text = strip_private_sections(md_text)
    text = convert_wikilinks(text, published_map, slug)
    md = markdown.Markdown(
        extensions=["extra", "sane_lists", "toc"],
        extension_configs={"toc": {"permalink": False}},
    )
    return md.convert(text)


def build_page(meta, body_html, slug, published_map):
    title = str(meta.get("title") or meta.get("name") or slug.replace("-", " "))
    desc = str(meta.get("description") or meta.get("summary") or "")[:150]
    eyebrow = str(meta.get("section") or meta.get("type") or "Notes")
    created = meta.get("created")
    meta_line = f"{created} · 持续修订" if created else "持续修订"

    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(t).lstrip("#") for t in tags if str(t).strip()]
    tags_block = ""
    if tags:
        inner = "".join(f"<span>{html.escape(t)}</span>" for t in tags)
        tags_block = f'  <div class="tags">{inner}</div>\n'

    return TEMPLATE.format(
        title=html.escape(title),
        desc=html.escape(desc),
        eyebrow=html.escape(eyebrow),
        meta_line=html.escape(meta_line),
        body=body_html,
        tags_block=tags_block,
    )


# ─────────────────────────── 主流程 ───────────────────────────
def collect(vault):
    out = []
    for dp, dns, fns in os.walk(vault):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in fns:
            if not f.endswith(".md"):
                continue
            p = Path(dp) / f
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            meta, body = split_frontmatter(text)
            if not is_published(meta):
                continue
            out.append((p, meta, body))
    return out


def slug_for(p, meta):
    s = meta.get("slug")
    if s:
        return re.sub(r"[^\w\-]+", "-", str(s)).strip("-").lower()
    return re.sub(r"[^\w\-]+", "-", p.stem).strip("-").lower() or "note"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault = Path(args.vault)
    if not vault.is_dir():
        sys.exit(f"库不存在: {vault}")

    items = collect(vault)
    print(f"扫描完成，publish: true 的笔记 {len(items)} 篇")
    if not items:
        print("没有可发布的笔记。要发布，在笔记 frontmatter 里加 publish: true")
        return 0

    # 先建立 slug 映射，供 wikilink 解析
    published_map = {}
    for p, meta, _ in items:
        published_map[p.stem] = slug_for(p, meta)

    if args.dry_run:
        for p, meta, _ in items:
            print(f"  {published_map[p.stem]:<34} <- {p.relative_to(vault)}")
        return 0

    out = Path(args.out)
    notes_dir = out / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    for p, meta, body in items:
        slug = published_map[p.stem]
        body_html = render(body, meta, published_map, slug)
        page = build_page(meta, body_html, slug, published_map)
        (notes_dir / f"{slug}.html").write_text(page, encoding="utf-8")
        print(f"  生成 {slug}.html")
        ok += 1

    print(f"完成：{ok} 篇")
    return 0


if __name__ == "__main__":
    sys.exit(main())
