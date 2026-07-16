#!/usr/bin/env python3
"""Build the SBM glossary page from the vault glossary -> glossary/index.html.

Source of truth = TWO vault markdown files, merged in order:
    W:/systems/glossary/glossary-sbm.md     (SBM-only terms)
    W:/systems/glossary/glossary-shared.md  (terms shared with MDDE)

The glossary was split by brand (2026-07-12): SBM-only, MDDE-only, and shared.
The SBM site renders sbm + shared; the MDDE site renders mdde + shared. Edit a
shared term once in glossary-shared.md and both sites pick it up. The intro comes
from glossary-sbm.md.

The glossary is the NON-concept vocabulary — field terms and distinctions that
deserve a shared definition and a link, but aren't ownable coined concepts
(those live in concepts/). It's a volatile, promotable layer: a term here can be
promoted to a concept page when it earns it.

This renders the glossary as a single grouped page. Terms reference concepts via
[[concept-<slug>]] wikilinks in the source; here they become links to the
concept detail pages (concepts/<slug>.html). Wikilinks whose target isn't a
concept slug (articles, other terms) render as plain text — the glossary never
links to a page that might not exist.

Design mirrors build_concepts.py (parse -> format-agnostic -> render_static), so
a WordPress renderer is a later addition, not a rewrite.

Usage:
    python build_glossary.py
    SBM_GLOSSARY_DIR="W:/systems/glossary" python build_glossary.py
"""
from __future__ import annotations

import os
import re
import html
from pathlib import Path
from dataclasses import dataclass, field

HERE = Path(__file__).parent
GLOSSARY_DIR = Path(os.environ.get("SBM_GLOSSARY_DIR", "W:/systems/glossary"))
SRC_SBM = GLOSSARY_DIR / "glossary-sbm.md"        # SBM-only terms (+ intro)
SRC_SHARED = GLOSSARY_DIR / "glossary-shared.md"  # terms shared with MDDE
OUT = HERE / "glossary"
CONCEPTS_DIR = HERE / "concepts"


def split_frontmatter(text: str) -> str:
    """Return the body after YAML frontmatter (frontmatter not needed here)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def known_concept_slugs() -> set[str]:
    """Slugs we can safely link to = the concept detail pages already built."""
    if not CONCEPTS_DIR.exists():
        return set()
    return {p.stem for p in CONCEPTS_DIR.glob("*.html") if p.stem != "index"}


@dataclass
class Term:
    name: str
    definition_md: str  # raw markdown of the definition (after the em dash)


@dataclass
class Group:
    title: str
    terms: list = field(default_factory=list)


def parse_glossary(src: Path) -> tuple[str, list[Group]]:
    """Return (intro_md, [Group]). Groups = '## ' sections; terms = '- **X** — ...'
    bullet lines within them. The intro is everything between the H1 and the first
    '## ' section (minus the format blockquote/rule)."""
    body = split_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
    lines = body.split("\n")
    groups: list[Group] = []
    intro_lines: list[str] = []
    cur: Group | None = None
    seen_h2 = False
    term_re = re.compile(r"^\s*-\s+\*\*(.+?)\*\*\s+[—-]\s+(.+)$")
    for ln in lines:
        st = ln.rstrip()
        if st.startswith("# ") and not seen_h2:
            continue  # skip H1 (page title comes from the template)
        if st.startswith("## "):
            seen_h2 = True
            if st[3:].strip().lower() == "cross-references":
                cur = None  # drop the trailing cross-references section
                continue
            cur = Group(title=st[3:].strip())
            groups.append(cur)
            continue
        if cur is not None:
            m = term_re.match(st)
            if m:
                cur.terms.append(Term(name=m.group(1).strip(),
                                      definition_md=m.group(2).strip()))
        elif not seen_h2:
            # intro material (skip the format blockquote and horizontal rules)
            if st.startswith(">") or st == "---":
                continue
            intro_lines.append(st)
    # keep groups that actually have terms
    groups = [g for g in groups if g.terms]
    intro = "\n".join(intro_lines).strip()
    return intro, groups


def merge_groups(groups: list[Group]) -> list[Group]:
    """Fold groups that share a title into one (case-insensitive), preserving
    first-seen order. Lets a brand file and the shared file both use e.g.
    'Data & modelling' without rendering two identical section headers."""
    out: list[Group] = []
    by_key: dict[str, Group] = {}
    for g in groups:
        key = g.title.strip().lower()
        if key in by_key:
            by_key[key].terms.extend(g.terms)
        else:
            ng = Group(title=g.title, terms=list(g.terms))
            by_key[key] = ng
            out.append(ng)
    return out


def esc(x: str) -> str:
    return html.escape(x or "", quote=False)


def render_inline(md: str, concept_slugs: set[str]) -> str:
    """Render a definition's inline markdown: [[concept-x]] -> link, **bold**,
    *italic*, `code`, and plain [[wikilink]] -> its label as text."""
    s = md

    # [[concept-slug|Label]] or [[concept-slug]] -> concept page link if known
    def _wikilink(m: "re.Match") -> str:
        target = m.group(1).strip()
        label = (m.group(2) or "").strip()
        slug = target[len("concept-"):] if target.startswith("concept-") else target
        display = label or (slug.replace("-", " ").title() if target.startswith("concept-") else target)
        if target.startswith("concept-") and slug in concept_slugs:
            return f'<a href="../concepts/{esc(slug)}.html">{esc(display)}</a>'
        return esc(display)  # unknown target (article, other index) -> plain text

    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _wikilink, s)
    # escape the rest, then re-apply the links we just built (stash them)
    stash: list[str] = []

    def _stash(m: "re.Match") -> str:
        stash.append(m.group(0))
        return f"\x00{len(stash)-1}\x00"

    s = re.sub(r"<a href=\"[^\"]+\">[^<]+</a>", _stash, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], s)
    return s


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
          <a href="../#why-structure">Why structure</a>
        </span>
      </span>
      <a href="../writing/">Writing</a>
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

STYLE = """<style>
  .gl-intro { max-width:760px; color:var(--ink-soft); font-size:16px; }
  .gl-group { margin-top:2.2rem; }
  .gl-group h2 { font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:var(--accent); margin:0 0 .8rem; }
  .gl-list { display:grid; gap:14px; }
  .gl-term { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px 20px; }
  .gl-term .t { font-size:17px; font-weight:800; color:var(--ink); margin-bottom:4px; }
  .gl-term .d { font-size:15px; color:var(--ink-soft); margin:0; line-height:1.55; }
  .gl-note { margin-top:2.2rem; font-size:14px; color:var(--ink-faint); border-top:1px solid var(--line); padding-top:1rem; }
</style>"""


def render(intro: str, groups: list[Group], concept_slugs: set[str]) -> str:
    body: list[str] = []
    for g in groups:
        body.append('<div class="gl-group">')
        body.append(f'<h2>{esc(g.title)}</h2>')
        body.append('<div class="gl-list">')
        for t in g.terms:
            body.append(
                '<div class="gl-term">'
                f'<div class="t">{esc(t.name)}</div>'
                f'<p class="d">{render_inline(t.definition_md, concept_slugs)}</p>'
                '</div>'
            )
        body.append('</div></div>')
    groups_html = "\n".join(body)
    intro_html = render_inline(intro.replace("\n", " "), concept_slugs) if intro else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Glossary · Structure Beats Magic</title>
<meta name="description" content="The non-concept vocabulary of Structure Beats Magic — field terms and distinctions defined and linked. A volatile layer under the concept library." />
<meta property="og:title" content="Glossary · Structure Beats Magic" />
<meta property="og:description" content="Field terms and distinctions, defined and linked — the vocabulary under the coined concepts." />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://structurebeatsmagic.com/glossary/" />
<meta property="og:image" content="https://structurebeatsmagic.com/assets/sbm-og-card.svg" />
<link rel="canonical" href="https://structurebeatsmagic.com/glossary/" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg"/>
<link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png"/>
<link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png"/>
<link rel="apple-touch-icon" sizes="180x180" href="../assets/favicon-180.png"/>
<link rel="stylesheet" href="../assets/site.css" />
{STYLE}
</head>
<body>

{NAV}

<div class="hero wrap">
  <div class="eyebrow">The vocabulary, defined</div>
  <h1>Glossary</h1>
  <p class="lede">{intro_html}</p>
</div>

<section id="glossary">
  <div class="wrap">
{groups_html}
    <p class="gl-note">A volatile, promotable layer: a term that keeps recurring or earns its own article gets promoted to a <a href="../concepts/">concept</a>. The coined concepts live in the <a href="../concepts/">concept library</a>.</p>
  </div>
</section>

{FOOTER}

{NAV_SCRIPT}
</body>
</html>
"""


def main() -> None:
    for src in (SRC_SBM, SRC_SHARED):
        if not src.exists():
            raise SystemExit(f"Glossary source not found: {src}")
    # SBM file supplies the intro + its own groups; shared file appends its groups.
    intro, groups = parse_glossary(SRC_SBM)
    _, shared_groups = parse_glossary(SRC_SHARED)
    groups = merge_groups(groups + shared_groups)
    concept_slugs = known_concept_slugs()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(render(intro, groups, concept_slugs), encoding="utf-8")
    n = sum(len(g.terms) for g in groups)
    print(f"  glossary/index.html ({n} terms in {len(groups)} groups: sbm + shared) -> {OUT}")


if __name__ == "__main__":
    main()
