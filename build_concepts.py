#!/usr/bin/env python3
"""
Build SBM concept pages from the vault concept library -> concepts/*.html.

Source of truth = the vault concept library (markdown, one file per concept):
    W:/systems/concepts/concept-*.md
Each concept has YAML frontmatter (name, description = the one-line tag,
metadata.category) + a body (the full explanation) + a "**Where it lives:**"
line. This script renders them into:

    concepts/index.html      — the overview: short cards (name + tag + summary)
                               grouped by category, each linking to a detail page.
    concepts/<slug>.html     — one detail page per concept: full explanation,
                               where-it-lives, and (when present in frontmatter)
                               related concepts / related articles / references.

"A brain that publishes itself", applied to the concept vocabulary: you keep the
concepts as markdown in the vault; this regenerates the site from them.

Design note — STATIC NOW, WORDPRESS-READY LATER:
The site is static HTML today but will migrate to WordPress. So the pipeline is
split cleanly: parse_concepts() turns the vault markdown into plain Concept data
objects (format-agnostic), and the render_* functions turn those into the current
static HTML. A future WordPress renderer is a second set of render_* functions
over the same Concept objects — not a rewrite. Pick the renderer with --format.

Usage:
    python build_concepts.py                 # static HTML (default)
    python build_concepts.py --format static
    SBM_CONCEPTS_SRC="W:/systems/concepts" python build_concepts.py
    # (WordPress renderer: to be added — see render_wordpress stub.)
"""
from __future__ import annotations

import os
import re
import sys
import html
from pathlib import Path

from image_pipeline import copy_optimised
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).parent
SRC = Path(os.environ.get("SBM_CONCEPTS_SRC", "W:/systems/concepts"))
OUT = HERE / "concepts"

# Canonical base for <link rel="canonical"> / og:url / absolute og:image on the
# generated concept pages (same convention as build_articles.py — the custom
# domain resolves directly to GitHub Pages since the 2026-06-30 DNS cutover).
BASE_URL = os.environ.get("SBM_BASE_URL", "https://structurebeatsmagic.com").rstrip("/")

# Category order for the index (authored sequence, mirrors the vault README TOC).
# Any category found in the sources but not listed here is appended at the end,
# so a new category can't silently drop a concept from the page.
CATEGORY_ORDER = [
    "Umbrella thesis",
    "Personal data model",
    "Filtering & identity",
    "Intelligence systems",
    "Method & workflow",
    "System architecture",
    "Brand & stance",
]

# Cross-cutting groups: a many-to-many overlay ON TOP of the one-per-concept
# category. A concept opts into a group via `groups: [<slug>]` in its frontmatter.
# Unlike categories (mutually exclusive), a concept can be in several groups.
# Each entry here gets a filter-chip on the index and its own /groups/<slug>.html
# overview page. A group referenced by a concept but missing here still gets a
# page (label = title-cased slug) — so a new group can't silently vanish.
GROUPS = {
    "layer-types": {
        "label": "Layer types",
        "blurb": "The named layers of the system — each a place with a boundary, "
                 "where something crosses, is transformed, or is concluded. A layer "
                 "is a role in the architecture, not a physical location (that's a "
                 "zone) and not a technique applied across it (that's a method).",
    },
}
GROUP_ORDER = ["layer-types"]

# Trailing working sections in a source file that must never be published.
PRIVATE_SECTIONS = {"notes", "actions", "comments", "briefs"}


# --------------------------------------------------------------------------- #
# Reusable markdown helpers (ported from build_articles.py, kept in sync)      #
# --------------------------------------------------------------------------- #
def split_frontmatter(text: str) -> tuple[dict, str]:
    # Same CRLF normalisation as build_articles.py: a file authored with CRLF
    # would otherwise have its frontmatter parsed as body text.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            meta = {}
            if yaml:
                try:
                    meta = yaml.safe_load(fm_raw) or {}
                except Exception as exc:
                    # Never swallow this. A malformed frontmatter block used to
                    # fail silently to {}, which published the article with no
                    # title, no subtitle and no hero -- a broken card on the
                    # index and a slug as the headline. One stray quote in a
                    # slop-audit note was enough. (2026-07-18)
                    print(f"  ! FRONTMATTER PARSE ERROR: {exc}")
                    meta = {"__parse_error__": str(exc)}
            return meta, body
    return {}, text


def strip_private_sections(body: str) -> str:
    lines = body.split("\n")
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith("## "):
            name = st[3:].strip().rstrip(":").lower()
            if name in PRIVATE_SECTIONS:
                return "\n".join(lines[:i]).rstrip() + "\n"
    return body


# Set once per run by render(): the slugs that will actually have a page. A
# [[wikilink]] to anything outside this set is rendered as plain text instead of
# a link, so a dangling reference can never ship as a 404. None = unknown (no
# filtering, e.g. when inline() is used standalone).
_known_concept_slugs: set | None = None
_dangling_links: list = []


def inline(s: str) -> str:
    """Escape + render [[wikilinks]], **bold**, *italic*, [text](url), `code`."""
    spans: list[str] = []

    def _stash(m: "re.Match") -> str:
        spans.append(html.escape(m.group(1), quote=False))
        return f"\x00{len(spans) - 1}\x00"

    # Obsidian [[wikilinks]] in body prose -> links to the concept detail page.
    # [[concept-slug|Label]] or [[concept-slug]]; the 'concept-' prefix is stripped
    # for the URL (pages are the bare slug), and a bare link derives a readable label.
    links: list[str] = []

    def _wiki(m: "re.Match") -> str:
        # Inside a markdown TABLE cell the alias pipe must be escaped (`\|`) or it
        # would split the cell -- so the backslash is part of the source, not the
        # slug. Strip it, or the link resolves to `<slug>\.html` -> 404.
        target = m.group(1).strip().rstrip("\\").strip()
        label = (m.group(2) or "").strip()
        bare = target[len("concept-"):] if target.startswith("concept-") else target
        if not label:
            label = bare.replace("-", " ").replace(" moc", " (MOC)")
            label = label[:1].upper() + label[1:]
        # Never emit a link to a concept that has no page: a dangling wikilink
        # (a concept that was renamed, lives in the MDDE library, or was never
        # written) becomes a 404 on a live page. Render the label as plain text
        # and let check_concept_links() report it.
        if _known_concept_slugs is not None and bare not in _known_concept_slugs:
            _dangling_links.append(bare)
            return html.escape(label, quote=False)
        links.append(f'<a href="{html.escape(bare, quote=True)}.html">{html.escape(label, quote=False)}</a>')
        return f"\x01{len(links) - 1}\x01"

    s = re.sub(r"\[\[([^\]|]+?)(?:\\?\|([^\]]+))?\]\]", _wiki, s)
    s = re.sub(r"`([^`]+)`", _stash, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)
    s = re.sub(r"\x01(\d+)\x01", lambda m: links[int(m.group(1))], s)
    return s


def md_to_html(md: str) -> str:
    """Minimal dependency-free markdown -> HTML. Supports headings, bold, italic,
    links, code fences, bullet lists, blockquotes, --- rules, paragraphs.
    Skips the leading H1 (title comes from frontmatter) and a leading italic lede.
    """
    lines = md.split("\n")
    out: list[str] = []
    para: list[str] = []
    bullets: list[str] = []
    quote: list[str] = []

    def flush_bullets():
        if bullets:
            items = "".join(f"<li>{inline(b)}</li>" for b in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()

    def flush_quote():
        if quote:
            joined = " ".join(quote).strip()
            if joined:
                out.append(f"<blockquote><p>{inline(joined)}</p></blockquote>")
            quote.clear()

    def flush():
        flush_bullets()
        flush_quote()
        if para:
            joined = " ".join(para).strip()
            if joined:
                out.append(f"<p>{inline(joined)}</p>")
            para.clear()

    first_h1_skipped = False
    lede_checked = False
    in_code = False
    code: list[str] = []
    for ln in lines:
        st = ln.strip()
        if st.startswith("```"):
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
                code.clear()
                in_code = False
            else:
                flush(); lede_checked = True; in_code = True
            continue
        if in_code:
            code.append(ln); continue
        if not st:
            flush(); continue
        if st.startswith("# ") and not first_h1_skipped:
            first_h1_skipped = True; continue
        if (first_h1_skipped and not lede_checked and not out and not para
                and st.startswith("*") and st.endswith("*") and not st.startswith("**")):
            lede_checked = True; continue
        lede_checked = True
        if st == "---":
            flush(); out.append("<hr/>"); continue
        if st.startswith("> "):
            flush_bullets()
            if para:
                flush()
            quote.append(st[2:].strip()); continue
        flush_quote()
        if st.startswith("### "):
            flush(); out.append(f"<h3>{inline(st[4:])}</h3>"); continue
        if st.startswith("## "):
            flush(); out.append(f"<h2>{inline(st[3:])}</h2>"); continue
        if st.startswith("# "):
            flush(); out.append(f"<h2>{inline(st[2:])}</h2>"); continue
        if st.startswith("- ") or (st.startswith("* ") and not st.startswith("**")):
            if para:
                flush()
            bullets.append(st[2:].strip()); continue
        flush_bullets()
        para.append(st)
    if in_code:
        out.append(f"<pre><code>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
    flush()
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Parse: vault markdown -> format-agnostic Concept objects                     #
# --------------------------------------------------------------------------- #
@dataclass
class Concept:
    slug: str          # page slug (source filename minus "concept-" prefix)
    name: str          # display name
    tag: str           # one-line tagline (frontmatter description)
    category: str      # grouping label
    summary: str       # first paragraph of the body, plain-ish (for the card)
    body_md: str       # full markdown body (minus the "Where it lives" tail meta)
    where: str         # "Where it lives" value (raw markdown), or ""
    groups: list = field(default_factory=list)              # [group-slug] (cross-cutting)
    related_concepts: list = field(default_factory=list)   # [slug or name]
    related_articles: list = field(default_factory=list)   # [{title,url}]
    references: list = field(default_factory=list)          # [{title,url}]
    hero_image: str = ""     # filename in the concept's assets/ (ADR-080 + ADR-075)
    hero_caption: str = ""   # optional caption rendered under the hero


def _norm_reflist(val) -> list:
    """Accept ['a','b'] or [{title,url}] or 'a' -> normalised list of dicts/strs."""
    if not val:
        return []
    if isinstance(val, str):
        return [val]
    out = []
    for v in val:
        if isinstance(v, dict):
            out.append({"title": str(v.get("title", "")).strip(),
                        "url": str(v.get("url", "")).strip()})
        else:
            out.append(str(v).strip())
    return out


def parse_concepts(src: Path) -> list[Concept]:
    concepts: list[Concept] = []
    # Folder-per-concept (ADR-080): each concept is <src>/<slug>/<slug>.md.
    # (Back-compat: also pick up any legacy flat concept-<slug>.md still present.)
    notes = [p for p in sorted(src.glob("*/*.md")) if p.stem == p.parent.name]
    notes += sorted(src.glob("concept-*.md"))
    for f in notes:
        text = f.read_text(encoding="utf-8", errors="replace")
        meta, body = split_frontmatter(text)
        body = strip_private_sections(body)
        slug = f.stem[len("concept-"):] if f.stem.startswith("concept-") else f.stem
        # The most reliable display name is the body's first H1 heading (correctly
        # capitalised, e.g. "A Toy vs an Instrument"). Fall back to frontmatter
        # title/name, then to a title-cased slug — so a broken frontmatter (e.g.
        # an unquoted "description:" with a colon) never yields an ugly name.
        name = ""
        m_h1 = re.search(r"^#\s+(.+)$", body, re.M)
        if m_h1:
            name = m_h1.group(1).strip()
        if not name:
            name = str(meta.get("title") or meta.get("name") or slug).strip()
            if name.startswith("concept-"):
                name = name[len("concept-"):].replace("-", " ").title()
        tag = str(meta.get("description", "")).strip()
        category = ""
        md = meta.get("metadata") or {}
        if isinstance(md, dict):
            category = str(md.get("category", "")).strip()
        category = category or "Other"

        # Cross-cutting groups: accept top-level `groups:` or nested under metadata.
        groups_raw = meta.get("groups")
        if not groups_raw and isinstance(md, dict):
            groups_raw = md.get("groups")
        groups = [str(g).strip() for g in groups_raw] if isinstance(groups_raw, list) \
            else ([str(groups_raw).strip()] if groups_raw else [])

        # Pull the "Where it lives:" line out of the body so it renders separately.
        where = ""
        body_lines = body.split("\n")
        kept: list[str] = []
        for ln in body_lines:
            m = re.match(r"\s*\*\*Where it lives:\*\*\s*(.+)$", ln)
            if m:
                where = m.group(1).strip()
                continue
            # drop the "← Back to [[concepts-index]]" navigation line
            if "Back to" in ln and "concepts-index" in ln:
                continue
            kept.append(ln)
        body_clean = "\n".join(kept).strip()

        # Also drop a redundant leading "**Category:** X" line if present
        # (the category is rendered as a chip on the detail page).
        body_clean = re.sub(r"^\s*\*\*Category:\*\*.*$", "", body_clean, flags=re.M).strip()

        # Drop a body "## Related concepts" section — the page renders its own
        # linked block from the frontmatter data (raw [[wikilinks]] would show
        # literally here). The wikilink version stays for reading in the vault.
        body_clean = re.sub(
            r"\n##+\s*Related concepts\s*\n.*?(?=\n##\s|\Z)",
            "\n", body_clean, flags=re.S | re.I,
        ).strip()

        # Summary for the card = the FIRST BODY PARAGRAPH — never the tagline.
        # The card already prints the tagline as .c-tag; reusing it here made every
        # card show the same sentence twice (blue, then grey). The summary's job is
        # to add what the tagline doesn't say: the first line of the explanation.
        # Falls back to the tagline only if the body has no usable paragraph.
        summary = ""
        for para in re.split(r"\n\s*\n", body_clean):
            p = " ".join(para.split())
            if not p or p.startswith(("#", ">", "**Category", "**Where", "←", "[[")):
                continue
            summary = p
            break
        if not summary:
            summary = tag
        # keep cards even: trim an over-long first paragraph on a word boundary
        if len(summary) > 240:
            summary = summary[:240].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "…"

        concepts.append(Concept(
            slug=slug, name=name, tag=tag, category=category,
            summary=summary, body_md=body_clean, where=where, groups=groups,
            # Accept relationship fields at top level OR nested under metadata:
            # (the vault concept generator writes them under metadata, mirroring
            # how category/groups are read above — one connected data model).
            related_concepts=_norm_reflist(meta.get("related_concepts") or (md.get("related_concepts") if isinstance(md, dict) else None)),
            related_articles=_norm_reflist(meta.get("related_articles") or (md.get("related_articles") if isinstance(md, dict) else None)),
            references=_norm_reflist(meta.get("references") or (md.get("references") if isinstance(md, dict) else None)),
            # optional concept hero (ADR-080 folder-per-concept + ADR-075 style):
            # <slug>/assets/<file>, copied into the site assets/ at build time.
            hero_image=str(meta.get("hero_image") or (md.get("hero_image") if isinstance(md, dict) else "") or "").strip().strip('"'),
            hero_caption=str(meta.get("hero_caption") or (md.get("hero_caption") if isinstance(md, dict) else "") or "").strip().strip('"'),
        ))
    return concepts


def group_concepts(concepts: list[Concept]) -> list[tuple[str, list[Concept]]]:
    by_cat: dict[str, list[Concept]] = {}
    for c in concepts:
        by_cat.setdefault(c.category, []).append(c)
    ordered: list[tuple[str, list[Concept]]] = []
    for cat in CATEGORY_ORDER:
        if cat in by_cat:
            ordered.append((cat, by_cat.pop(cat)))
    for cat in sorted(by_cat):  # any leftover categories, alphabetical
        ordered.append((cat, by_cat[cat]))
    return ordered


def collect_groups(concepts: list[Concept]) -> list[tuple[str, dict, list[Concept]]]:
    """Cross-cutting groups -> [(slug, meta{label,blurb}, members)] in GROUP_ORDER,
    then any group used-but-unregistered (label = title-cased slug), alphabetical.
    A group with no members is dropped."""
    members: dict[str, list[Concept]] = {}
    for c in concepts:
        for g in c.groups:
            members.setdefault(g, []).append(c)
    ordered: list[tuple[str, dict, list[Concept]]] = []
    seen = set()
    for slug in GROUP_ORDER:
        if slug in members:
            ordered.append((slug, GROUPS.get(slug, {"label": slug.replace("-", " ").title(), "blurb": ""}), members[slug]))
            seen.add(slug)
    for slug in sorted(members):
        if slug not in seen:
            ordered.append((slug, GROUPS.get(slug, {"label": slug.replace("-", " ").title(), "blurb": ""}), members[slug]))
    return ordered


# --------------------------------------------------------------------------- #
# Render: Concept objects -> static HTML (site.css skeleton)                   #
# --------------------------------------------------------------------------- #
NAV = """<header class="site">
  <div class="wrap">
    <a class="brand" href="../">Structure&nbsp;Beats&nbsp;<span>Magic</span></a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Open menu" />
    <label for="nav-toggle" class="burger" aria-hidden="true"><span></span><span></span><span></span></label>
    <nav class="main">
      <span class="navgroup">
        <button class="navtop" type="button">Thesis</button>
        <span class="navmenu">
          <a href="../#principles">Principles</a>
          <a href="../concepts/">Concepts</a>
          <a href="../glossary/">Glossary</a>
          <a href="../#play">Play</a>
          <a href="../#why-structure">Why structure</a>
        </span>
      </span>
      <span class="navgroup">
        <button class="navtop" type="button">System</button>
        <span class="navmenu">
          <a href="../system/">How the system works</a>
          <a href="../intelligence/">Intelligence systems</a>
        </span>
      </span>
      <span class="navgroup">
        <button class="navtop" type="button">Proof</button>
        <span class="navmenu">
          <a href="../#use-cases">Sample systems</a>
          <a href="../influences/">Influences</a>
          <a href="../#about">About Jaco</a>
        </span>
      </span>
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
  .concept-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:20px; }
  .concept { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:22px 24px; box-shadow:0 1px 2px rgba(15,23,42,.04); transition:box-shadow .15s ease, transform .15s ease; text-decoration:none; display:block; }
  a.concept:hover { box-shadow:0 4px 14px rgba(15,23,42,.08); transform:translateY(-1px); }
  .concept .c-name { font-size:19px; font-weight:800; letter-spacing:-.01em; color:var(--ink); margin-bottom:6px; }
  .concept .c-tag { font-size:14px; font-weight:600; color:var(--accent); margin-bottom:10px; }
  .concept .c-def { font-size:15px; color:var(--ink-soft); margin:0; }
  /* Section heading — used identically for a CATEGORY and for a cross-cutting
     GROUP, because both are ways of grouping the same concepts. Left-aligned
     with a rule, so the eye reads: heading -> its cards -> next heading. */
  .cat-head { display:flex; align-items:baseline; gap:.75rem; margin:3.25rem 0 1.25rem; }
  .cat-head:first-of-type { margin-top:1rem; }
  .cat-head h2 { font-size:22px; font-weight:800; letter-spacing:-.01em; color:var(--ink); margin:0; white-space:nowrap; }
  .cat-head h2 a { color:inherit; text-decoration:none; }
  .cat-head h2 a:hover { color:var(--accent); }
  .cat-head .cat-count { font-size:14px; font-weight:600; color:var(--ink-faint); }
  .cat-head .cat-rule { flex:1 1 auto; height:1px; background:var(--line); }
  /* A group says what it is; a category doesn't need to. */
  .cat-note { font-size:14px; color:var(--ink-faint); margin:-.5rem 0 1.25rem; max-width:70ch; line-height:1.6; }
  /* Optional scene-band above a category (ADR-075 track B). Thin, rounded,
     face-safe crop. Present only when assets/cat-<slug>.jpg exists. */
  .cat-band { margin:3.25rem 0 0; border-radius:14px; overflow:hidden; border:1px solid var(--line); box-shadow:0 6px 20px rgba(15,23,42,.06); }
  .cat-band + .cat-head { margin-top:1rem; }
  .cat-band img { width:100%; height:130px; object-fit:cover; object-position:center 40%; display:block; }
  @media (max-width:760px){ .concept-grid{ grid-template-columns:1fr; } .cat-band img{ height:100px; } }
</style>"""

DETAIL_STYLE = """<style>
  .c-detail { max-width:760px; }
  .c-crumb { font-size:14px; margin-bottom:1rem; }
  .c-chip { display:inline-block; font-size:12px; font-weight:700; letter-spacing:.02em; text-transform:uppercase; color:var(--accent); background:rgba(37,99,235,.08); border-radius:999px; padding:4px 12px; margin-bottom:1rem; }
  a.c-chip-group { text-decoration:none; border:1px solid rgba(37,99,235,.25); background:transparent; transition:background .15s ease; }
  a.c-chip-group:hover { background:rgba(37,99,235,.10); }
  a.c-chip-group::before { content:"◆ "; opacity:.55; }
  .c-tagline { font-size:20px; font-weight:600; color:var(--ink); border-left:3px solid var(--accent); padding-left:16px; margin:0 0 1.5rem; }
  .c-hero { margin:0 0 2rem; }
  .c-hero img { width:100%; height:auto; display:block; border-radius:12px; border:1px solid var(--line); box-shadow:0 10px 30px rgba(15,23,42,.07); }
  .c-hero figcaption { font-size:.85rem; color:var(--ink-faint); margin-top:.7rem; text-align:center; line-height:1.5; }
  /* the concept's own namesake article -- the way in, not a "related" link */
  .c-canonical { margin:0 0 1.15rem; font-size:17px; line-height:1.6; }
  .c-canonical a { font-weight:600; }
  .c-body { font-size:17px; line-height:1.75; color:var(--ink-soft); }
  .c-body p { margin:0 0 1.15rem; }
  .c-body p:last-child { margin-bottom:0; }
  .c-body ul { margin:0 0 1.15rem; padding-left:1.15rem; }
  .c-body li { margin:.35rem 0; }
  .c-body h2 { font-size:20px; color:var(--ink); margin-top:2rem; margin-bottom:.6rem; }
  .c-rel { margin-top:2rem; border-top:1px solid var(--line); padding-top:1.5rem; }
  .c-rel h3 { font-size:14px; text-transform:uppercase; letter-spacing:.03em; color:var(--ink-faint); margin:0 0 .6rem; }
  .c-rel ul { margin:0 0 1.2rem; padding-left:1.1rem; }
  .c-rel li { font-size:15px; margin:.3rem 0; }
</style>"""


def esc(x: str) -> str:
    return html.escape(x or "", quote=False)


def _concept_card(c: Concept) -> str:
    return (
        f'<a class="concept" href="{esc(c.slug)}.html">'
        f'<div class="c-name">{esc(c.name)}</div>'
        f'<div class="c-tag">{esc(c.tag)}</div>'
        f'<p class="c-def">{esc(c.summary)}</p></a>'
    )


def _section(title: str, items: list[Concept], note: str = "", href: str = "") -> list[str]:
    """One index section: heading + count + rule, then the concept cards.

    Used for BOTH categories and cross-cutting groups — they're two ways of
    grouping the same concepts, so they render identically. Previously a group
    was demoted to a chip in the corner while a category got a full section,
    which is the inconsistency Jaco kept (rightly) pointing at.
    """
    head = ['<div class="cat-head">']
    head.append(f'<h2><a href="{esc(href)}">{esc(title)}</a></h2>' if href else f'<h2>{esc(title)}</h2>')
    head.append(f'<span class="cat-count">{len(items)}</span>')
    head.append('<span class="cat-rule"></span>')
    head.append('</div>')
    out = []
    # Optional scene-band (ADR-075 track B): if assets/cat-<slug>.jpg exists it is
    # rendered as a thin banner above the heading. Missing file => plain heading
    # (graceful, like hero_image). Slug = title lowercased, non-alnum -> hyphen.
    _cat_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    _band = HERE / "assets" / f"cat-{_cat_slug}.jpg"
    if _band.exists():
        out.append(f'<div class="cat-band"><img src="../assets/cat-{_cat_slug}.jpg" '
                   f'alt="{esc(title)}" loading="lazy" /></div>')
    out.append("".join(head))
    if note:
        out.append(f'<p class="cat-note">{esc(note)}</p>')
    out.append('<div class="concept-grid">')
    out.extend(_concept_card(c) for c in items)
    out.append('</div>')
    return out


def render_index(groups: list[tuple[str, list[Concept]]],
                 xgroups: list[tuple[str, dict, list[Concept]]] | None = None) -> str:
    chips_html = ""   # groups are rendered as sections now, not as a chip bar

    parts: list[str] = []
    for cat, items in groups:
        parts.extend(_section(cat, items))

    # Cross-cutting groups, same shape as a category. A concept has exactly one
    # category but MAY belong to groups, so its card appears in both places —
    # that repetition is the point: it's a second, deliberate way in.
    for slug, gmeta, members in (xgroups or []):
        label = gmeta.get("label", slug.replace("-", " ").title())
        parts.extend(_section(
            label, members,
            note=gmeta.get("blurb", ""),
            href=f"groups/{slug}.html",
        ))

    groups_html = "\n".join(parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Concepts &amp; vocabulary · Structure Beats Magic</title>
<meta name="description" content="The named concepts of Structure Beats Magic — the coined vocabulary of knowledge management re-architected for the AI era." />
<meta property="og:title" content="Concepts &amp; vocabulary · Structure Beats Magic" />
<meta property="og:description" content="The coined vocabulary behind the thesis — one memorable name per idea, each with its own page." />
<meta property="og:type" content="website" />
<meta property="og:url" content="{BASE_URL}/concepts/" />
<meta property="og:image" content="{BASE_URL}/assets/sbm-og-card.svg" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="canonical" href="{BASE_URL}/concepts/" />
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg"/>
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png"/>
<link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="../assets/favicon-180.png"/>
<link rel="stylesheet" href="../assets/site.css" />
{INDEX_STYLE}
<!-- Google Analytics (GA4) — shared property with jacovanderlaan.com -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-P7W9B34R1Z"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', 'G-P7W9B34R1Z');
</script>
</head>
<body>

{NAV}

<div class="hero wrap">
  <div class="eyebrow">The vocabulary</div>
  <h1>Concepts &amp; vocabulary</h1>
  <p class="lede">A thesis earns its own words. These are the named concepts behind Structure Beats Magic — one memorable name per idea, so it can be pointed at, reused, and built on. Click any concept for the full picture. Not jargon for its own sake; a shared language for a system you can actually run.</p>
</div>

<section id="concepts">
  <div class="wrap">
    <div class="section-eyebrow">The vocabulary</div>
    <h2 class="section-title">Named concepts</h2>
    <p class="section-lede">The coined terms this thesis owns — grouped by where they live in the system. Each links to its own page.</p>
{chips_html}
{groups_html}
    <p class="infl-note" style="margin-top:2rem">A living vocabulary — it grows as the thesis does. For field terms and distinctions that aren't coined concepts, see the <a href="../glossary/">glossary</a>. The enterprise counterpart (Model-Driven Data Engineering) keeps its own concept library at <a href="https://jacovanderlaan.com/concepts.html">jacovanderlaan.com/concepts</a>.</p>
  </div>
</section>

{FOOTER}

{NAV_SCRIPT}
</body>
</html>
"""


# NAV/FOOTER for group pages live one level deeper (concepts/groups/), so the
# relative prefix is "../../" instead of "../". Build depth-adjusted copies.
def _reprefix(html_block: str) -> str:
    return (html_block
            .replace('href="../', 'href="../../')
            .replace('src="../', 'src="../../'))


def render_group(slug: str, gmeta: dict, members: list[Concept]) -> str:
    nav = _reprefix(NAV)
    footer = _reprefix(FOOTER)
    label = gmeta.get("label", slug.replace("-", " ").title())
    blurb = gmeta.get("blurb", "")
    # Members keep authored order within the group (source-sorted from parse).
    cards = "".join(
        f'<a class="concept" href="../{esc(c.slug)}.html">'
        f'<div class="c-name">{esc(c.name)}</div>'
        f'<div class="c-tag">{esc(c.tag)}</div>'
        f'<p class="c-def">{esc(c.summary)}</p></a>'
        for c in members
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(label)} · Concepts · Structure Beats Magic</title>
<meta name="description" content="{html.escape(blurb, quote=True)}" />
<meta property="og:title" content="{esc(label)} · Structure Beats Magic" />
<meta property="og:description" content="{html.escape(blurb, quote=True)}" />
<meta property="og:type" content="website" />
<meta property="og:url" content="{BASE_URL}/concepts/groups/{esc(slug)}.html" />
<meta property="og:image" content="{BASE_URL}/assets/sbm-og-card.svg" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="canonical" href="{BASE_URL}/concepts/groups/{esc(slug)}.html" />
<link rel="icon" type="image/svg+xml" href="../../assets/favicon.svg"/>
<link rel="icon" type="image/png" sizes="32x32" href="../../assets/favicon-32.png"/>
<link rel="icon" type="image/png" sizes="16x16" href="../../assets/favicon-16.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="../../assets/favicon-180.png"/>
<link rel="stylesheet" href="../../assets/site.css" />
{INDEX_STYLE}
<!-- Google Analytics (GA4) — shared property with jacovanderlaan.com -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-P7W9B34R1Z"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', 'G-P7W9B34R1Z');
</script>
</head>
<body>

{nav}

<div class="hero wrap">
  <div class="c-crumb" style="font-size:14px;margin-bottom:1rem"><a href="../">&#8592; All concepts</a></div>
  <div class="eyebrow">Concept group</div>
  <h1>{esc(label)}</h1>
  <p class="lede">{esc(blurb)}</p>
</div>

<section id="concepts">
  <div class="wrap">
    <div class="section-eyebrow">The group</div>
    <h2 class="section-title">{esc(label)} <span style="color:var(--ink-faint);font-weight:600">({len(members)})</span></h2>
    <p class="section-lede">Every concept tagged into this group, drawn from across the categories. A concept can belong to more than one group.</p>
    <div class="concept-grid">
{cards}
    </div>
    <p class="infl-note" style="margin-top:2rem">&#8592; Back to <a href="../">all concepts</a>.</p>
  </div>
</section>

{footer}

{NAV_SCRIPT}
</body>
</html>
"""


def _render_rel_block(concepts_by_slug, concepts_by_name, c: Concept) -> str:
    def resolve(ref):
        # ref is a slug or a display name; link to the detail page if we can.
        # Tolerate the vault convention of a "concept-" prefix on slugs
        # (frontmatter writes concept-<slug>; page slugs are the bare <slug>).
        key = str(ref).strip()
        bare = key[len("concept-"):] if key.startswith("concept-") else key
        target = (concepts_by_slug.get(key) or concepts_by_slug.get(bare)
                  or concepts_by_name.get(key.lower()))
        if target:
            return f'<a href="{esc(target.slug)}.html">{esc(target.name)}</a>'
        return esc(key)

    blocks: list[str] = []
    if c.related_concepts:
        items = "".join(f"<li>{resolve(r)}</li>" for r in c.related_concepts)
        blocks.append(f"<h3>Related concepts</h3><ul>{items}</ul>")
    if c.related_articles:
        # An article with the concept's own slug is not "related" -- it IS the
        # canonical piece for this concept. Promote it to its own line above the
        # list so the reader gets the obvious route in, and "Related writing"
        # keeps its plain meaning: the OTHER articles that reference this idea.
        def _slug_of(a):
            if isinstance(a, dict) and a.get("url"):
                return a["url"].rstrip("/").split("/")[-1].removesuffix(".html")
            return None

        canonical = next((a for a in c.related_articles if _slug_of(a) == c.slug), None)
        others = [a for a in c.related_articles if a is not canonical]

        if canonical:
            blocks.append(
                f'<h3>The article</h3><p class="c-canonical">'
                f'<a href="{html.escape(canonical["url"], quote=True)}">'
                f'{esc(canonical.get("title") or canonical["url"])}</a></p>'
            )
        if others:
            lis = []
            for a in others:
                if isinstance(a, dict) and a.get("url"):
                    lis.append(f'<li><a href="{html.escape(a["url"], quote=True)}">{esc(a.get("title") or a["url"])}</a></li>')
                elif isinstance(a, dict):
                    lis.append(f'<li>{esc(a.get("title",""))}</li>')
                else:
                    lis.append(f'<li>{esc(str(a))}</li>')
            blocks.append(f'<h3>Related writing</h3><ul>{"".join(lis)}</ul>')
    if c.references:
        lis = []
        for r in c.references:
            if isinstance(r, dict) and r.get("url"):
                lis.append(f'<li><a href="{html.escape(r["url"], quote=True)}">{esc(r.get("title") or r["url"])}</a></li>')
            elif isinstance(r, dict):
                lis.append(f'<li>{esc(r.get("title",""))}</li>')
            else:
                lis.append(f'<li>{esc(str(r))}</li>')
        blocks.append(f'<h3>References</h3><ul>{"".join(lis)}</ul>')
    if not blocks:
        return ""
    return '<div class="c-rel">' + "".join(blocks) + '</div>'


def render_detail(c: Concept, concepts_by_slug, concepts_by_name) -> str:
    body_html = md_to_html(c.body_md)
    # "Where it lives" (c.where) is an internal/technical note and is intentionally NOT
    # published on concept pages. The field is still parsed and kept on the Concept for
    # internal use; it is simply not rendered here.
    rel_html = _render_rel_block(concepts_by_slug, concepts_by_name, c)
    # Group memberships as chips next to the category chip (link to group pages).
    group_chips = "".join(
        f' <a class="c-chip c-chip-group" href="groups/{esc(g)}.html">'
        f'{esc(GROUPS.get(g, {}).get("label", g.replace("-", " ").title()))}</a>'
        for g in c.groups
    )
    # optional concept hero (ADR-080): <slug>/assets/<file> -> site assets/
    # Render only when the image exists on disk: a brief may set hero_image long
    # before the image is generated, and an <img> at a missing file would ship a
    # broken image to the site.
    hero_html = ""
    og_image = f"{BASE_URL}/assets/sbm-og-card.svg"
    if c.hero_image and (SRC / c.slug / "assets" / c.hero_image).is_file():
        cap = f"<figcaption>{esc(c.hero_caption)}</figcaption>" if c.hero_caption else ""
        hero_html = (f'<figure class="c-hero"><img src="../assets/{esc(c.hero_image)}" '
                     f'alt="{esc(c.name)}" loading="eager"/>{cap}</figure>')
        # the concept's own hero makes a far richer social card than the generic one
        og_image = f"{BASE_URL}/assets/{c.hero_image}"
    canonical = f"{BASE_URL}/concepts/{c.slug}.html"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(c.name)} · Concepts · Structure Beats Magic</title>
<meta name="description" content="{html.escape(c.tag, quote=True)}" />
<meta property="og:title" content="{esc(c.name)} · Structure Beats Magic" />
<meta property="og:description" content="{html.escape(c.tag, quote=True)}" />
<meta property="og:type" content="article" />
<meta property="og:url" content="{esc(canonical)}" />
<meta property="og:image" content="{esc(og_image)}" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="canonical" href="{esc(canonical)}" />
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg"/>
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png"/>
<link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="../assets/favicon-180.png"/>
<link rel="stylesheet" href="../assets/site.css" />
{DETAIL_STYLE}
</head>
<body>

{NAV}

<div class="hero wrap">
  <div class="c-crumb"><a href="./">&#8592; All concepts</a></div>
  <div class="c-chip">{esc(c.category)}</div>{group_chips}
  <h1>{esc(c.name)}</h1>
</div>

<section>
  <div class="wrap c-detail">
    <p class="c-tagline">{esc(c.tag)}</p>
    {hero_html}
    <div class="c-body">
{body_html}
    </div>
    {rel_html}
  </div>
</section>

{FOOTER}

{NAV_SCRIPT}
</body>
</html>
"""


def copy_concept_assets(concepts: list[Concept]) -> int:
    """Copy each concept's own assets/ into the site assets/ (build output).

    Mirrors the article builder: the concept folder owns its images
    (<root>/<slug>/assets/*), and the repo assets/ is generated — never
    hand-managed. Only concepts that declare a hero_image need this.
    """
    site_assets = HERE / "assets"
    site_assets.mkdir(parents=True, exist_ok=True)
    copied = 0
    for c in concepts:
        if not c.hero_image:
            continue
        src = SRC / c.slug / "assets" / c.hero_image
        if src.is_file():
            copy_optimised(src, site_assets / c.hero_image)
            copied += 1
        else:
            print(f"  ! concept hero missing on disk: {c.slug} -> {c.hero_image}")
    return copied


def render_static(concepts: list[Concept]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n = copy_concept_assets(concepts)
    if n:
        print(f"  copied {n} concept hero image(s) -> assets/")
    groups = group_concepts(concepts)
    xgroups = collect_groups(concepts)
    by_slug = {c.slug: c for c in concepts}
    by_name = {c.name.lower(): c for c in concepts}
    # index (with cross-cutting group chips)
    (OUT / "index.html").write_text(render_index(groups, xgroups), encoding="utf-8")
    # detail pages
    for c in concepts:
        (OUT / f"{c.slug}.html").write_text(
            render_detail(c, by_slug, by_name), encoding="utf-8")
    # cross-cutting group pages -> concepts/groups/<slug>.html
    if xgroups:
        gdir = OUT / "groups"
        gdir.mkdir(parents=True, exist_ok=True)
        for slug, gmeta, members in xgroups:
            (gdir / f"{slug}.html").write_text(
                render_group(slug, gmeta, members), encoding="utf-8")
    print(f"  index.html + {len(concepts)} detail pages + "
          f"{len(xgroups)} group page(s) -> {OUT}")


def render_wordpress(concepts: list[Concept]) -> None:
    # STUB for the future WordPress migration. The parse step already produces
    # format-agnostic Concept objects; a WordPress renderer would map each to a
    # post/CPT (e.g. via WP REST API or a WXR export) reusing name/tag/body_md/
    # category/related_*. Kept as a stub so the pipeline is provably format-split.
    raise SystemExit("WordPress renderer not implemented yet — the pipeline is "
                     "WP-ready (Concept objects are format-agnostic), but only "
                     "the static renderer is built. See render_static().")


# Article sources whose frontmatter declares related_concepts. We invert those
# edges so each concept page can show "which articles reference this concept".
# Both brands' article roots are scanned; a concept slug maps to the articles
# (title + published URL) that list it in related_concepts.
ARTICLE_ROOTS = [
    (Path(os.environ.get("SBM_ARTICLES_SRC", "W:/systems/products/sbm/articles")),
     "https://structurebeatsmagic.com/articles"),
    (Path(os.environ.get("MDDE_ARTICLES_SRC", "W:/data/products/mdde/articles")),
     "https://jacovanderlaan.com/articles"),
]


def _bare_concept_slug(ref: str) -> str:
    r = str(ref).strip()
    return r[len("concept-"):] if r.startswith("concept-") else r


def _published_article_slugs():
    """The set of slugs the site actually publishes = build_articles.ARTICLES.
    Imported (not duplicated) so the two builders can never drift apart.
    Returns None if it can't be read -- callers then skip the publish filter
    rather than silently dropping every link."""
    try:
        import build_articles
        arts = getattr(build_articles, "ARTICLES", None)
        if not arts:
            return None
        out = set()
        for a in arts:
            out.add(a if isinstance(a, str) else (a.get("slug") or a.get("name")))
        return {s for s in out if s} or None
    except Exception:
        return None


def build_reverse_article_index(published_slugs=None) -> dict:
    """concept-slug -> [{title, url}] for every PUBLISHED article that lists it
    in related_concepts/concepts. The reverse of the article->concept edge, so a
    concept page can show the articles that reference it.

    published_slugs: restrict to these slugs (defaults to the article builder's
    ARTICLES allow-list). Pass an empty set to disable linking entirely."""
    if yaml is None:
        return {}
    if published_slugs is None:
        published_slugs = _published_article_slugs()
    idx: dict = {}
    for root, base_url in ARTICLE_ROOTS:
        if not root.exists():
            continue
        for md in root.glob("*/*.md"):
            if md.stem != md.parent.name:          # only folder-notes <slug>/<slug>.md
                continue
            txt = md.read_text(encoding="utf-8")
            if not txt.startswith("---"):
                continue
            end = txt.find("\n---", 3)
            if end == -1:
                continue
            try:
                meta = yaml.safe_load(txt[3:end]) or {}
            except Exception:
                continue
            # Two frontmatter spellings mean the same thing (a list of concept
            # slugs): `related_concepts` (7 articles) and `concepts` (25). Both
            # are the article->concept edge, so read both and merge -- otherwise
            # three quarters of the corpus never reaches a concept page.
            rc = meta.get("related_concepts") or []
            if not isinstance(rc, list):
                rc = [rc]
            cs = meta.get("concepts") or []
            if not isinstance(cs, list):
                cs = [cs]
            refs = list(rc) + list(cs)
            if not refs:
                continue
            slug = md.stem
            # Only link articles that are actually published: the site's publish
            # gate is build_articles.ARTICLES (an allow-list), NOT frontmatter
            # `status`. Linking a draft would put a 404 on a live concept page.
            if published_slugs is not None and slug not in published_slugs:
                continue
            title = str(meta.get("title", slug)).strip().strip('"')
            entry = {"title": title, "url": f"{base_url}/{slug}.html"}
            for ref in refs:
                idx.setdefault(_bare_concept_slug(ref), []).append(entry)
    # stable order + de-dup per concept
    for k, lst in idx.items():
        seen, uniq = set(), []
        for e in lst:
            if e["url"] in seen:
                continue
            seen.add(e["url"]); uniq.append(e)
        idx[k] = sorted(uniq, key=lambda e: e["title"].lower())
    return idx


def check_hero_refs(concepts: list[Concept]) -> None:
    """Report both hero-image failure modes. Warning-only, by design.

    Unlike the article builder (which renders <img> blindly and so must FAIL on a
    missing file), the concept renderer already skips a hero whose file isn't on
    disk — it cannot ship a broken image. But it fails *silently*, which hides two
    real mistakes:

      1. hero_image set, file missing -> the hero just vanishes, no warning. A
         typo in the filename looks identical to "no hero yet".
      2. hero file on disk, never referenced -> the graphic was delivered but
         nothing points at it, so it never publishes. This happened twice
         (federated-brains, rent-the-ai-own-the-structure).

    Neither breaks a page, so neither fails the build — but both are silent work
    that went nowhere, and both are worth seeing in the build output.
    """
    missing, orphans = [], []
    for c in concepts:
        adir = SRC / c.slug / "assets"
        if c.hero_image and not (adir / c.hero_image).is_file():
            missing.append(f"{c.slug}: hero_image -> no file 'assets/{c.hero_image}' (hero will NOT render)")
        if adir.is_dir():
            for f in sorted(adir.iterdir()):
                if (f.is_file() and "hero" in f.name.lower()
                        and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp")
                        and f.name != c.hero_image):
                    orphans.append(f"{c.slug}: 'assets/{f.name}' exists but no hero_image points at it")
    for m in missing:
        print(f"  ! {m}")
    for o in orphans:
        print(f"  ~ {o}")
    if missing or orphans:
        print(f"  ({len(missing)} missing-file, {len(orphans)} unreferenced — hero refs need attention)")


def main() -> None:
    fmt = "static"
    args = sys.argv[1:]
    if "--format" in args:
        i = args.index("--format")
        if i + 1 < len(args):
            fmt = args[i + 1]
    if not SRC.exists():
        raise SystemExit(f"Concept source not found: {SRC}")
    concepts = parse_concepts(SRC)
    print(f"Parsed {len(concepts)} concepts from {SRC}")
    # Tell the wikilink resolver which concepts will actually have a page, so a
    # [[link]] to a missing one renders as text rather than shipping a 404.
    global _known_concept_slugs, _dangling_links
    _known_concept_slugs = {c.slug for c in concepts}
    _dangling_links = []
    check_hero_refs(concepts)
    # attach reverse edges: articles that reference each concept (related_concepts)
    rev = build_reverse_article_index()
    linked = 0
    for c in concepts:
        arts = rev.get(c.slug)
        if not arts:
            continue
        have = {a.get("url") for a in c.related_articles if isinstance(a, dict)}
        c.related_articles = list(c.related_articles) + [a for a in arts if a["url"] not in have]
        linked += 1
    print(f"Reverse-linked related articles onto {linked} concepts")
    if _dangling_links:
        from collections import Counter
        print(f"  ! {len(set(_dangling_links))} dangling [[wikilink]] target(s) rendered as PLAIN TEXT "
              f"(no such concept page -- would have been a 404):")
        for slug, n in sorted(Counter(_dangling_links).items()):
            print(f"      [[{slug}]]  x{n}")
        print("    Fix: create the concept, retarget the link, or drop it.")
    if fmt == "static":
        render_static(concepts)
    elif fmt == "wordpress":
        render_wordpress(concepts)
    else:
        raise SystemExit(f"Unknown --format: {fmt} (use static|wordpress)")
    print("Done.")


if __name__ == "__main__":
    main()
