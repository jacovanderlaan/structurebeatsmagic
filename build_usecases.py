#!/usr/bin/env python3
"""
Build SBM use-case pages from the vault use-case library -> use-cases/*.html.

Source of truth = W:/systems/use-cases/*.md (one file per use case; ADR-069).
A use case = the method applied to one concrete situation (teaching/demo unit).

Renders:
    use-cases/index.html      — overview cards (title + badge + summary), linking to detail pages.
    use-cases/<slug>.html     — one detail page per use case: full body, applies-to
                                concepts, related articles, optional demo link.

Same pipeline shape as build_concepts.py: parse -> format-agnostic UseCase
objects -> render_static (a WordPress renderer is a future second renderer over
the same objects). Mirrors the site skeleton (site.css + shared NAV/FOOTER).

Usage:  python build_usecases.py
        SBM_USECASES_SRC="W:/systems/use-cases" python build_usecases.py
"""
from __future__ import annotations

import os
import re
import html
from pathlib import Path
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).parent
SRC = Path(os.environ.get("SBM_USECASES_SRC", "W:/systems/use-cases"))
OUT = HERE / "use-cases"
CONCEPTS_DIR = "../concepts"   # for linking applies-to concepts to their pages
ARTICLES_DIR = "../articles"   # for linking related articles

SKIP = {"readme", "inventory-2026-07-07"}
PRIVATE_SECTIONS = {"notes", "actions", "comments", "briefs"}

# --- markdown helpers (kept in sync with build_concepts.py) ---
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
    lines = body.split("\n")
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith("## "):
            if st[3:].strip().rstrip(":").lower() in PRIVATE_SECTIONS:
                return "\n".join(lines[:i]).rstrip() + "\n"
    return body


def inline(s: str) -> str:
    spans: list[str] = []
    def _stash(m):
        spans.append(html.escape(m.group(1), quote=False))
        return f"\x00{len(spans)-1}\x00"
    s = re.sub(r"`([^`]+)`", _stash, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)
    return s


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    out, para, bullets = [], [], []
    def flush_b():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()
    def flush():
        flush_b()
        if para:
            j = " ".join(para).strip()
            if j: out.append(f"<p>{inline(j)}</p>")
            para.clear()
    h1_skipped = False
    for ln in lines:
        st = ln.strip()
        if not st:
            flush(); continue
        if st.startswith("# ") and not h1_skipped:
            h1_skipped = True; continue
        if st == "---":
            flush(); out.append("<hr/>"); continue
        if st.startswith("### "):
            flush(); out.append(f"<h3>{inline(st[4:])}</h3>"); continue
        if st.startswith("## "):
            flush(); out.append(f"<h2>{inline(st[3:])}</h2>"); continue
        if st.startswith("- ") or (st.startswith("* ") and not st.startswith("**")):
            if para: flush()
            bullets.append(st[2:].strip()); continue
        flush_b()
        para.append(st)
    flush()
    return "\n".join(out)


# --- parse: markdown -> UseCase objects ---
@dataclass
class UseCase:
    slug: str
    title: str
    badge: str
    summary: str
    body_md: str
    concepts: list = field(default_factory=list)         # concept slugs
    related_articles: list = field(default_factory=list) # article slugs
    demo_url: str = ""


def _titlecase(slug: str) -> str:
    return slug.replace("-", " ").title()


def parse_usecases(src: Path) -> list[UseCase]:
    ucs: list[UseCase] = []
    for f in sorted(src.glob("*.md")):
        if f.stem.lower() in SKIP:
            continue
        meta, body = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if str(meta.get("type", "")).lower() != "use-case":
            continue
        body = strip_private_sections(body)
        # slug: drop a leading date prefix (2026-07-04_) if present
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", f.stem)
        title = str(meta.get("title", "")).strip() or _titlecase(slug)
        title = re.sub(r"^Use Case\s*[—:-]\s*", "", title)  # drop "Use Case — " prefix
        badge = str(meta.get("badge", "") or meta.get("kind", "")).strip()
        summary = str(meta.get("summary", "") or meta.get("situation", "")).strip()
        concepts = [str(c).strip() for c in (meta.get("concepts") or []) if str(c).strip()]
        rel = [str(a).strip() for a in (meta.get("related_articles") or []) if str(a).strip()]
        demo = str(meta.get("demo_url", "") or "").strip()
        ucs.append(UseCase(slug=slug, title=title, badge=badge, summary=summary,
                           body_md=body, concepts=concepts, related_articles=rel,
                           demo_url=demo))
    return ucs


# --- render ---
NAV = """<header class="site">
  <div class="wrap">
    <a class="brand" href="../">Structure&nbsp;Beats&nbsp;<span>Magic</span></a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Open menu" />
    <label for="nav-toggle" class="burger" aria-hidden="true"><span></span><span></span><span></span></label>
    <nav class="main">
      <span class="navgroup"><button class="navtop" type="button">Thesis</button>
        <span class="navmenu">
          <a href="../#principles">Principles</a><a href="../concepts/">Concepts</a>
          <a href="../#play">Play</a><a href="../#why-structure">Why structure</a>
        </span></span>
      <span class="navgroup"><button class="navtop" type="button">Proof</button>
        <span class="navmenu">
          <a href="../use-cases/">Use cases</a><a href="../#about">About Jaco</a>
        </span></span>
      <a href="../#writing">Writing</a>
      <a class="nav-cta" href="https://jacovanderlaan.com">For enterprises &#8594;</a>
    </nav>
  </div>
</header>"""

FOOTER = """<footer>
  <div class="wrap">
    <div class="formula-mini">Structure + Data + AI + Rules + Skills &#8594; Systems</div>
    <div>Structure Beats Magic — a thesis by <a href="https://jacovanderlaan.com">Jaco van der Laan</a></div>
  </div>
</footer>"""

NAV_SCRIPT = """<script>
  var t = document.getElementById('nav-toggle');
  document.querySelectorAll('nav.main a').forEach(function(a){
    a.addEventListener('click', function(){ if (t) t.checked = false; });
  });
</script>"""

INDEX_STYLE = """<style>
  .uc-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:20px; }
  .uc { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:22px 24px; box-shadow:0 1px 2px rgba(15,23,42,.04); transition:box-shadow .15s ease, transform .15s ease; text-decoration:none; display:block; }
  a.uc:hover { box-shadow:0 4px 14px rgba(15,23,42,.08); transform:translateY(-1px); }
  .uc .uc-badge { font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--gold); margin-bottom:8px; }
  .uc .uc-name { font-size:19px; font-weight:800; letter-spacing:-.01em; color:var(--ink); margin-bottom:8px; }
  .uc .uc-sum { font-size:15px; color:var(--ink-soft); margin:0; }
  @media (max-width:760px){ .uc-grid{ grid-template-columns:1fr; } }
</style>"""

DETAIL_STYLE = """<style>
  .uc-detail { max-width:760px; }
  .uc-crumb { font-size:14px; margin-bottom:1rem; }
  .uc-chip { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--gold); background:rgba(184,138,27,.10); border-radius:999px; padding:4px 12px; margin-bottom:1rem; }
  .uc-body { font-size:17px; line-height:1.65; color:var(--ink-soft); }
  .uc-body h2 { font-size:20px; color:var(--ink); margin-top:1.6rem; }
  .uc-cta { margin:1.5rem 0; }
  .uc-rel { margin-top:2rem; border-top:1px solid var(--line); padding-top:1.5rem; }
  .uc-rel h3 { font-size:14px; text-transform:uppercase; letter-spacing:.03em; color:var(--ink-faint); margin:0 0 .6rem; }
  .uc-rel ul { margin:0 0 1.2rem; padding-left:1.1rem; }
  .uc-rel li { font-size:15px; margin:.3rem 0; }
</style>"""


def esc(x: str) -> str:
    return html.escape(x or "", quote=False)


def render_index(ucs: list[UseCase]) -> str:
    cards = []
    for u in ucs:
        cards.append(
            f'<a class="uc" href="{esc(u.slug)}.html">'
            f'{f"<div class=\"uc-badge\">{esc(u.badge)}</div>" if u.badge else ""}'
            f'<div class="uc-name">{esc(u.title)}</div>'
            f'<p class="uc-sum">{esc(u.summary)}</p></a>'
        )
    grid = '<div class="uc-grid">' + "\n".join(cards) + '</div>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Use cases · Structure Beats Magic</title>
<meta name="description" content="The method applied to real jobs — use cases where Structure Beats Magic lands on one concrete situation: real data, real structure, real output." />
<meta property="og:title" content="Use cases · Structure Beats Magic" />
<meta property="og:description" content="Proof, not slides — the thesis applied to concrete situations." />
<meta property="og:type" content="website" />
<meta property="og:image" content="../assets/sbm-og-card.svg" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="stylesheet" href="../assets/site.css" />
{INDEX_STYLE}
</head>
<body>

{NAV}

<div class="hero wrap">
  <div class="eyebrow">Proof, not slides</div>
  <h1>Use cases</h1>
  <p class="lede">A use case is the thesis landed on one concrete situation — real data, real structure, real output. Not a slide about what's possible; a working system you can see. Click any use case for the full picture.</p>
</div>

<section id="use-cases">
  <div class="wrap">
    <div class="section-eyebrow">Proof, not slides</div>
    <h2 class="section-title">The method applied to a real job</h2>
    <p class="section-lede">Each shows Structure Beats Magic working for one situation. The recipe is here for free; the kitchen is where the work happens.</p>
{grid}
  </div>
</section>

{FOOTER}

{NAV_SCRIPT}
</body>
</html>
"""


def render_detail(u: UseCase, article_titles: dict) -> str:
    body_html = md_to_html(u.body_md)
    cta = (f'<div class="uc-cta"><a class="btn btn-primary" href="{html.escape(u.demo_url, quote=True)}">See how it\'s built &#8594;</a></div>'
           if u.demo_url else "")
    rel_blocks = []
    if u.concepts:
        items = "".join(
            f'<li><a href="{CONCEPTS_DIR}/{esc(c)}.html">{esc(_titlecase(c))}</a></li>'
            for c in u.concepts)
        rel_blocks.append(f"<h3>Applies these concepts</h3><ul>{items}</ul>")
    if u.related_articles:
        items = "".join(
            f'<li><a href="{ARTICLES_DIR}/{esc(a)}.html">{esc(article_titles.get(a, _titlecase(a)))}</a></li>'
            for a in u.related_articles)
        rel_blocks.append(f"<h3>Related writing</h3><ul>{items}</ul>")
    rel_html = ('<div class="uc-rel">' + "".join(rel_blocks) + "</div>") if rel_blocks else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(u.title)} · Use cases · Structure Beats Magic</title>
<meta name="description" content="{html.escape(u.summary, quote=True)}" />
<meta property="og:title" content="{esc(u.title)} · Structure Beats Magic" />
<meta property="og:description" content="{html.escape(u.summary, quote=True)}" />
<meta property="og:type" content="article" />
<meta property="og:image" content="../assets/sbm-og-card.svg" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="stylesheet" href="../assets/site.css" />
{DETAIL_STYLE}
</head>
<body>

{NAV}

<div class="hero wrap">
  <div class="uc-crumb"><a href="./">&#8592; All use cases</a></div>
  {f'<div class="uc-chip">{esc(u.badge)}</div>' if u.badge else ''}
  <h1>{esc(u.title)}</h1>
</div>

<section>
  <div class="wrap uc-detail">
    <div class="uc-body">
{body_html}
    </div>
    {cta}
    {rel_html}
  </div>
</section>

{FOOTER}

{NAV_SCRIPT}
</body>
</html>
"""


def article_title_map() -> dict:
    """Best-effort: read published article titles for nicer related-links."""
    titles = {}
    art_root = Path(os.environ.get("SBM_ARTICLES_ROOT", "W:/systems/products/sbm/articles"))
    if art_root.exists():
        for md in art_root.rglob("*.md"):
            if md.stem != md.parent.name:
                continue
            meta, _ = split_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            t = str(meta.get("title", "")).strip().strip('"')
            if t:
                titles[md.stem] = t
    return titles


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Use-case source not found: {SRC}")
    ucs = parse_usecases(SRC)
    print(f"Parsed {len(ucs)} use cases from {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    titles = article_title_map()
    (OUT / "index.html").write_text(render_index(ucs), encoding="utf-8")
    for u in ucs:
        (OUT / f"{u.slug}.html").write_text(render_detail(u, titles), encoding="utf-8")
    print(f"  index.html + {len(ucs)} detail pages -> {OUT}")
    print("Done.")


if __name__ == "__main__":
    main()
