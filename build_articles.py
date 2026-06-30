#!/usr/bin/env python3
"""
Build SBM article pages from markdown drafts -> articles/*.html + a writing index.

Source of truth = the markdown drafts (you keep writing in markdown). This script
renders them into styled static HTML that matches the hub. "A brain that publishes
itself", applied to the hub's own writing.

Usage:
    python build_articles.py
    SBM_DRAFTS="W:/.../drafts" python build_articles.py   # override source

Drafts must have YAML frontmatter with at least `title`; optional `subtitle`,
`face`, `created`. Only files listed in ARTICLES (or, if empty, all dated drafts
matching the SBM series) are published — so unrelated drafts in the folder stay
private.
"""
from __future__ import annotations

import os
import re
import html
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).parent
DRAFTS = Path(os.environ.get(
    "SBM_DRAFTS",
    "W:/data/products/mdde/output/articles/drafts",
))
OUT = HERE / "articles"

# Explicit allow-list: only these drafts publish to the SBM hub (filename stem).
# Keeps the shared drafts folder from leaking unrelated/MDDE pieces.
ARTICLES = [
    "2026-06-29_Your-Photos-Are-Already-a-Map",
    "2026-06-29_Your-Bookshelf-Is-Already-a-Knowledge-Base",
    "2026-06-29_Your-Trips-Are-Already-Structured-Data-Part-1",
    "2026-06-29_Your-Trips-Are-Already-Structured-Data-Part-2",
    "2026-06-28_The-Filter-Youre-Missing-Anti-Interests",
    "2026-06-28_What-Youre-Not-Is-Also-Who-You-Are",
    "2026-06-29_Stop-Prompting-Start-Directing",
    "2026-06-29_A-Brain-That-Publishes-Itself",
]

CSS = "../assets/article.css"


def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            meta = {}
            if yaml:
                try:
                    meta = yaml.safe_load(fm_raw) or {}
                except Exception:
                    meta = {}
            return meta, body
    return {}, text


def md_to_html(md: str) -> str:
    """Minimal, dependency-free markdown -> HTML for our article style.

    Supports: # ## ### headings, **bold**, *italic*, [text](url), --- rules,
    paragraphs. Deliberately small — our drafts use a narrow markdown subset.
    """
    # strip the leading H1 (we render title from frontmatter) + leading italic lede
    lines = md.split("\n")
    out: list[str] = []
    para: list[str] = []
    bullets: list[str] = []

    def flush_bullets():
        if bullets:
            items = "".join(f"<li>{inline(b)}</li>" for b in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()

    def flush():
        flush_bullets()
        if para:
            joined = " ".join(para).strip()
            if joined:
                out.append(f"<p>{inline(joined)}</p>")
            para.clear()

    def inline(s: str) -> str:
        # Pull inline-code spans (`code`) out first so their contents are never
        # touched by the bold/italic/link passes, then restore as <code>.
        spans: list[str] = []

        def _stash(m: "re.Match") -> str:
            spans.append(html.escape(m.group(1), quote=False))
            return f"\x00{len(spans) - 1}\x00"

        s = re.sub(r"`([^`]+)`", _stash, s)
        s = html.escape(s, quote=False)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        # Bold first (non-greedy, so a paragraph that is entirely **bold** and
        # contains *italic* inside still matches), then italic on what remains.
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)
        return s

    first_h1_skipped = False
    lede_checked = False
    in_code = False
    code: list[str] = []
    for ln in lines:
        st = ln.strip()
        # fenced code block: ``` ... ``` — capture lines verbatim, preserving
        # whitespace/newlines (ASCII diagrams, CLI output). No inline formatting.
        if st.startswith("```"):
            if in_code:
                code_html = html.escape("\n".join(code), quote=False)
                out.append(f"<pre><code>{code_html}</code></pre>")
                code.clear()
                in_code = False
            else:
                flush()
                lede_checked = True
                in_code = True
            continue
        if in_code:
            code.append(ln)
            continue
        if not st:
            flush()
            continue
        if st.startswith("# ") and not first_h1_skipped:
            first_h1_skipped = True
            continue
        # Skip a leading italic lede paragraph (`*...*` on its own) right after the
        # H1 — it duplicates the frontmatter subtitle, which we render separately.
        if (first_h1_skipped and not lede_checked and not out and not para
                and st.startswith("*") and st.endswith("*")
                and not st.startswith("**")):
            lede_checked = True
            continue
        lede_checked = True
        if st == "---":
            flush()
            out.append("<hr/>")
            continue
        # figure shortcode:  [[figure: filename.png | optional caption]]
        if st.startswith("[[figure:") and st.endswith("]]"):
            flush()
            inner = st[len("[[figure:"):-2].strip()
            fn, _, cap = inner.partition("|")
            fn = fn.strip()
            cap = cap.strip()
            cap_html = f"<figcaption>{inline(cap)}</figcaption>" if cap else ""
            out.append(f'<figure class="article-fig"><img src="../assets/{fn}" '
                       f'alt="{cap or fn}" loading="lazy"/>{cap_html}</figure>')
            continue
        if st.startswith("### "):
            flush(); out.append(f"<h3>{inline(st[4:])}</h3>"); continue
        if st.startswith("## "):
            flush(); out.append(f"<h2>{inline(st[3:])}</h2>"); continue
        if st.startswith("# "):
            flush(); out.append(f"<h2>{inline(st[2:])}</h2>"); continue
        # bullet list item: "- text" or "* text" (not "**bold**")
        if (st.startswith("- ") or (st.startswith("* ") and not st.startswith("**"))):
            if para:
                flush()  # close any open paragraph before starting the list
            bullets.append(st[2:].strip())
            continue
        flush_bullets()  # a non-bullet line ends any open list
        para.append(st)
    if in_code:  # unclosed fence — emit what we captured rather than drop it
        code_html = html.escape("\n".join(code), quote=False)
        out.append(f"<pre><code>{code_html}</code></pre>")
    flush()
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title} — Structure Beats Magic</title>
<meta name="description" content="{subtitle}"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{subtitle}"/>
<meta property="og:type" content="article"/>
<meta property="og:image" content="{og_image}"/>
<link rel="stylesheet" href="{css}"/>
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="../">Structure&nbsp;Beats&nbsp;<span>Magic</span></a>
  <a class="back" href="../#writing">← All writing</a>
</div></header>
<main class="wrap article">
  <p class="eyebrow">{face}</p>
  <h1>{title}</h1>
  <p class="subtitle">{subtitle}</p>
  <div class="byline">By Jaco van der Laan{date}</div>
  {hero}
  <article>
  {body}
  </article>
  <div class="article-cta">
    <p class="formula-mini">Structure + Data + AI + Rules + Skills → Systems</p>
    <a class="btn" href="../#writing">← More writing</a>
    <a class="btn btn-ghost" href="https://jacovanderlaan.com">Work with Jaco →</a>
  </div>
</main>
<footer><div class="wrap">Structure Beats Magic — a thesis by
  <a href="https://jacovanderlaan.com">Jaco van der Laan</a></div></footer>
</body></html>
"""


def face_label(meta: dict) -> str:
    f = str(meta.get("face", ""))
    if f.lower().startswith("b2c"):
        return "For knowledge workers"
    if f.lower().startswith("b2b"):
        return "For builders &amp; teams"
    return "Structure Beats Magic"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    cards = []
    for stem in ARTICLES:
        src = DRAFTS / f"{stem}.md"
        if not src.exists():
            print(f"  ! missing draft: {src}")
            continue
        meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
        title = str(meta.get("title", stem)).strip().strip('"')
        subtitle = str(meta.get("subtitle", "")).strip().strip('"')
        created = str(meta.get("created", "")).strip().strip("'\"")
        date = f" · {created}" if created else ""
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", stem).lower()
        out_path = OUT / f"{slug}.html"
        # optional hero image: frontmatter `hero_image:` (filename in assets/),
        # with optional `hero_caption:`. Rendered after the byline.
        hero = ""
        hi = str(meta.get("hero_image", "")).strip().strip("'\"")
        if hi:
            cap = str(meta.get("hero_caption", "")).strip().strip("'\"")
            cap_html = f'<figcaption>{html.escape(cap)}</figcaption>' if cap else ""
            hero = (f'<figure class="article-hero"><img src="../assets/{hi}" '
                    f'alt="{html.escape(title, quote=True)}" loading="eager"/>{cap_html}</figure>')
        og_image = f"../assets/{hi}" if hi else "../assets/sbm-og-card.svg"
        out_path.write_text(PAGE.format(
            title=html.escape(title, quote=True),
            subtitle=html.escape(subtitle, quote=True),
            face=face_label(meta),
            date=date,
            hero=hero,
            og_image=og_image,
            body=md_to_html(body),
            css=CSS,
        ), encoding="utf-8")
        print(f"  + articles/{slug}.html")
        cards.append((created, title, subtitle, f"articles/{slug}.html", face_label(meta)))

    # write a snippet the homepage can include (manual paste or future include)
    cards.sort(reverse=True)
    snip = []
    for _d, title, subtitle, href, face in cards:
        snip.append(
            f'      <a class="post" href="{href}">'
            f'<span class="post-face">{face}</span>'
            f'<h3>{html.escape(title)}</h3>'
            f'<p>{html.escape(subtitle)}</p></a>'
        )
    (OUT / "_cards.html").write_text("\n".join(snip), encoding="utf-8")
    print(f"  + articles/_cards.html ({len(cards)} cards)")


if __name__ == "__main__":
    main()
