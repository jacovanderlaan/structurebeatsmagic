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
import json
import shutil
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).parent
# SBM article source home. Folder-per-article (2026-07-04): each published article
# is a folder under ARTICLES_ROOT whose name is the slug, containing:
#   <slug>/<slug>.md      the folder-note = the article source (frontmatter + body)
#   <slug>/assets/*       this article's images (hero + infographics)
#   <slug>/notes|actions|comments.md   private working files (NOT published)
# The builder copies each article's assets/ into the repo assets/ at build time,
# so repo assets/ is a build output — no more hand-managed drift.
ARTICLES_ROOT = Path(os.environ.get(
    "SBM_ARTICLES_ROOT",
    "W:/systems/products/sbm/articles",
))
OUT = HERE / "articles"
ASSETS = HERE / "assets"

# Private-section convention: the folder-note is one markdown document. Everything
# publishes EXCEPT a fixed set of working sections at the bottom. As soon as the
# builder hits the first of these (case-insensitive ## heading), it stops
# publishing — the rest is a private notes/actions/comments summary. Mirrors the
# vault's protected manual-sections rule.
PRIVATE_SECTIONS = {"notes", "actions", "comments", "briefs"}

# Explicit allow-list of article slugs (folder names). Only these publish.
ARTICLES = [
    "the-pkm-and-ai-dividing-line",
    "zettelkasten-2-0",
    "governing-what-your-ai-can-touch",
    "the-image-integrity-gate",
    "your-notes-are-brain-cells",
    "why-structure-beats-magic",
    "your-photos-are-already-a-map",
    "your-bookshelf-is-already-a-knowledge-base",
    "your-trips-are-already-structured-data-part-1",
    "your-trips-are-already-structured-data-part-2",
    "the-filter-youre-missing-anti-interests",
    "what-youre-not-is-also-who-you-are",
    "stop-prompting-start-directing",
    "a-brain-that-publishes-itself",
]

CSS = "../assets/article.css"

# Canonical base for sitemap URLs. DNS cutover completed 2026-06-30: the custom
# domain structurebeatsmagic.com now resolves directly to GitHub Pages (apex
# A-records 185.199.108-111.153 + www CNAME), so it is the live canonical home.
BASE_URL = os.environ.get(
    "SBM_BASE_URL",
    "https://structurebeatsmagic.com",
).rstrip("/")


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


def strip_private_sections(body: str) -> str:
    """Cut the body at the first private working section.

    The folder-note is one markdown document; everything publishes except the
    trailing working sections (## Notes, ## Actions, ## Comments, ## Briefs).
    We stop at the first such ## heading so those never reach the published HTML.
    """
    lines = body.split("\n")
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith("## "):
            name = st[3:].strip().rstrip(":").lower()
            if name in PRIVATE_SECTIONS:
                return "\n".join(lines[:i]).rstrip() + "\n"
    return body


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
<meta name="author" content="Jaco van der Laan"/>
<link rel="canonical" href="{canonical}"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{subtitle}"/>
<meta property="og:type" content="article"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:site_name" content="Structure Beats Magic"/>
<meta property="og:image" content="{og_image_abs}"/>
<meta property="article:author" content="Jaco van der Laan"/>{published_meta}
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{title}"/>
<meta name="twitter:description" content="{subtitle}"/>
<meta name="twitter:image" content="{og_image_abs}"/>
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg"/>
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png"/>
<link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="../assets/favicon-180.png"/>
<link rel="stylesheet" href="{css}"/>
<script type="application/ld+json">
{json_ld}
</script>
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


def build_article_jsonld(title: str, subtitle: str, canonical: str,
                         image_abs: str, created: str) -> str:
    """Build a JSON-LD Article schema block.

    The author is a Person entity linked (via sameAs) to Jaco's other public
    profiles, so Google can unify "Jaco van der Laan" across sites and rank
    these articles for name searches. publisher = the SBM brand. datePublished
    is emitted only when known.
    """
    author = {
        "@type": "Person",
        "name": "Jaco van der Laan",
        "url": "https://jacovanderlaan.com",
        "sameAs": [
            "https://jacovanderlaan.com",
            "https://www.linkedin.com/in/jacovanderlaan",
            "https://medium.com/@jacovanderlaan",
        ],
    }
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": subtitle,
        "image": image_abs,
        "author": author,
        "publisher": {
            "@type": "Organization",
            "name": "Structure Beats Magic",
            "url": BASE_URL,
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "url": canonical,
    }
    if created:
        data["datePublished"] = created
        data["dateModified"] = created
    return json.dumps(data, indent=2, ensure_ascii=False)


def face_label(meta: dict) -> str:
    f = str(meta.get("face", ""))
    if f.lower().startswith("b2c"):
        return "For knowledge workers"
    if f.lower().startswith("b2b"):
        return "For builders &amp; teams"
    return "Structure Beats Magic"


def copy_article_assets(slug: str) -> int:
    """Copy an article folder's assets/* into the repo assets/ (build output).

    Makes repo assets/ a derived artifact — the source of truth for an article's
    images is <slug>/assets/. Returns the number of files copied.
    """
    src_dir = ARTICLES_ROOT / slug / "assets"
    if not src_dir.is_dir():
        return 0
    ASSETS.mkdir(exist_ok=True)
    n = 0
    for f in sorted(src_dir.iterdir()):
        if f.is_file():
            shutil.copy2(f, ASSETS / f.name)
            n += 1
    return n


def main() -> None:
    OUT.mkdir(exist_ok=True)
    cards = []
    for slug in ARTICLES:
        folder = ARTICLES_ROOT / slug
        src = folder / f"{slug}.md"
        if not src.exists():
            print(f"  ! missing folder-note: {src}")
            continue
        copied = copy_article_assets(slug)
        meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
        body = strip_private_sections(body)
        title = str(meta.get("title", slug)).strip().strip('"')
        subtitle = str(meta.get("subtitle", "")).strip().strip('"')
        created = str(meta.get("created", "")).strip().strip("'\"")
        date = f" · {created}" if created else ""
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
        # SEO: canonical URL, absolute OG image, author + publish-date metadata,
        # and JSON-LD Article schema. The canonical is what makes syndication
        # (Medium etc.) safe — it tells Google this site is the original home.
        canonical = f"{BASE_URL}/articles/{slug}.html"
        og_image_abs = (f"{BASE_URL}/assets/{hi}" if hi
                        else f"{BASE_URL}/assets/sbm-og-card.svg")
        published_meta = (f'\n<meta property="article:published_time" content="{created}"/>'
                          if created else "")
        json_ld = build_article_jsonld(title, subtitle, canonical, og_image_abs, created)
        out_path.write_text(PAGE.format(
            title=html.escape(title, quote=True),
            subtitle=html.escape(subtitle, quote=True),
            face=face_label(meta),
            date=date,
            hero=hero,
            canonical=canonical,
            og_image_abs=og_image_abs,
            published_meta=published_meta,
            json_ld=json_ld,
            body=md_to_html(body),
            css=CSS,
        ), encoding="utf-8")
        print(f"  + articles/{slug}.html  ({copied} assets)")
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

    write_sitemap(cards)


def write_sitemap(cards: list) -> None:
    """Regenerate sitemap.xml from the published pages, so it stays current.

    Lists the hub + section pages + every published article. Excludes 404.html
    and the _cards.html fragment. Article lastmod uses its `created` date.
    """
    # known article lastmod by relative href
    art_dates = {href: (d or "") for d, _t, _s, href, _f in cards}
    urls: list[tuple[str, str]] = []  # (relative path, lastmod)

    # top-level + section pages (no reliable date -> omit lastmod)
    for rel in ["", "system/", "intelligence/", "influences/"]:
        urls.append((rel, ""))

    # published articles, sorted newest first
    for href in sorted(art_dates, key=lambda h: art_dates[h], reverse=True):
        urls.append((href, art_dates[href]))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for rel, lastmod in urls:
        loc = f"{BASE_URL}/{rel}" if rel else f"{BASE_URL}/"
        parts.append("  <url>")
        parts.append(f"    <loc>{html.escape(loc)}</loc>")
        if lastmod:
            parts.append(f"    <lastmod>{html.escape(lastmod)}</lastmod>")
        parts.append("  </url>")
    parts.append("</urlset>")
    (HERE / "sitemap.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"  + sitemap.xml ({len(urls)} urls, base {BASE_URL})")


if __name__ == "__main__":
    main()
