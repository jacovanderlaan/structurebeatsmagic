# Structure Beats Magic — site style, voice & SEO guide

The single reference for how this site is written, designed, structured and found.
Read this before editing copy, adding a section, or dropping in a new infographic.
Sister enterprise site (`jacovanderlaan.com`) shares the palette and much of the
voice — keep them visually and tonally consistent.

---

## 1. Brand & positioning (what the site is)

- **Master brand:** *Structure Beats Magic* — the umbrella thesis. Knowledge
  Management, re-architected for the AI era.
- **One-line thesis:** "The magic isn't in the model. It's in the structure you
  give it."
- **The formula (always this order):** `Structure + Data + AI + Rules + Skills → Systems`.
  Rules is the deliberate climax — "the missing word" everyone forgets. Skills is
  repeatable capability. Systems (in gold) is the payoff.
- **Brand architecture:** this hub gives the *what/why* free (the recipe) and
  routes the *how/method* to paid engagements at jacovanderlaan.com (the kitchen).
  "Give the recipe, sell the kitchen."
- **Two audiences, one formula:** route content by **audience, not domain** —
  knowledge-workers (B2C, the audience engine) and builders/teams/orgs (B2B, the
  cash lane). Personal proof feeds business credibility.
- **NOT "PKM".** We say *Knowledge Management re-architected for the AI era*. PKM
  is the consumer-grade MVP of what a disciplined vault already does.
- **Thesis, not framework.** Position as a thinker/practitioner with a point of
  view, never a product or a certifiable framework to sell.

## 2. Voice & tone (how it sounds)

- **First person, calm, declarative.** Jaco speaking — "I built…", "the work was…".
  Confident without hype. No exclamation marks, no emoji in body copy.
- **Plain over clever.** Short sentences. Concrete nouns. "Boring is what still
  works next year." Earn trust by being specific, not by selling.
- **Show proof, not slides.** Always ground claims in the real numbers
  (155,000 photos, 271 books, a decade of trips) and real systems. "Proof, not
  slides." Never fabricate metrics, reviews, or testimonials — a personal thesis
  site dies on a fake "4.9/5 from 1,842 users".
- **The honest counterweight.** Every strong claim gets its caveat: structure
  beats magic *only when the structure is usable*; don't over-build; AI reduces
  the problem, doesn't remove it — still verify. Credibility comes from naming the
  limits.
- **Signature lines** (reuse, don't overuse): "Structure beats magic." · "Give
  the recipe, sell the kitchen." · "A toy vs an instrument." · "Rent the AI; own
  the structure." · "Notes organize. Architecture personalizes."
- **British-ish spelling** in body copy is fine (organise, visualise) — keep a
  given page internally consistent.
- **Em dashes** for asides — used freely, the house punctuation. Curly quotes.
- **AI-tell avoidance:** no "delve", "tapestry", "in today's fast-paced world",
  "unlock/unleash/supercharge", "game-changer", "elevate". No three-item rule-of-
  three padding. If a sentence sounds like a chatbot, cut it.

## 3. Layout & design rules (how it looks)

### Palette (CSS custom properties in `assets/site.css`)
| Token | Value | Use |
|---|---|---|
| `--bg` | `#f7f8fa` | page background (off-white) |
| `--surface` | `#fff` | cards |
| `--ink` | `#0f172a` | primary text / deep navy |
| `--ink-soft` | `#475569` | secondary text, ledes |
| `--ink-faint` | `#94a3b8` | captions, meta |
| `--accent` | `#2563eb` | brand blue — links, CTAs, eyebrows |
| `--accent-dk` | `#1e40af` | hover |
| `--gold` | `#b88a1b` | the payoff / "Systems" / climax only — use sparingly |
| `--line` | `#e2e8f0` | borders |

- **Type:** Inter / system sans. Eyebrows are uppercase, letter-spaced, accent
  colour. Section titles large and tight (`letter-spacing:-.02em`).
- **Formula styling:** navy pill, gold arrow + gold result.

### Generating the infographics (ChatGPT)
Every infographic is generated in ChatGPT, **one concept per image** — never a dense
numbered multi-panel sheet. If an image comes back as a grid or with panel numbers,
it's wrong for this site — regenerate as a single concept, no numbering. The reusable
ChatGPT master prompt and the per-slot briefs are kept **private** (input, not
publication) in the vault, not in this repo:
`D:/vault/personal/career/2-active/positioning/2026-06-29_infographic-image-briefs-chatgpt.md`.

### IMAGE RULE (important — frequently violated)
**Never stack two `<figure>` elements back-to-back without a substantial text
block (≈25+ words: a paragraph, card grid, or list) between them.** Two images
touching looks like a dump and kills rhythm.

- One figure per text block. Interleave figures *among* the prose, don't pile them
  at the end of a section.
- When new infographics arrive and a section would end up with 2+ stacked:
  **re-evaluate, keep the single best for that spot, and relocate the others** to
  sections where they're separated by text (or to another page entirely). Drop
  true duplicates rather than placing both.
- Prefer the most on-message image for each concept; move overlapping
  process/pipeline diagrams apart so they don't compete.
- Audit before committing (regex: consecutive `<figure>…</figure>` with <25 words
  of stripped text between them = a violation).

### Where specific content lives
- **Data-architecture / MDDE method visuals** (Kimball→stars, lineage, SCD2, the
  "Visual Guides" series) belong on **jacovanderlaan.com** (`mdde.html`), NOT on
  SBM — that's the enterprise method, the paid lane.
- **"Stop Prompting / Directing" infographic series** → the *Stop-Prompting-Start-
  Directing* article (a representative subset; don't dump all 36 panels).
- **Photo / knowledge-graph / modeled-self visuals** → SBM homepage
  (why-structure, next-level) and `/system`.

## 4. Structure & navigation (how it's organised)

- **Static-first (ADR-046):** plain HTML + shared `assets/site.css`. No framework,
  no runtime on the hub. The travel-curation sample site uses Astro separately.
- **Pages:** `/` (hub) · `/system/` (how it works) · `/intelligence/` (intelligence
  systems) · `/influences/` (references) · `/articles/*` (writing).
- **Nav = 5 compact dropdown groups** (Thesis · System · Proof · Writing ·
  enterprise CTA), hover on desktop, inline-expand on mobile (CSS-only hamburger,
  breakpoint `max-width:860px`). Don't exceed ~5 top-level items.
- **Section pattern:** `eyebrow → section-title → section-lede → content`. Long
  pages (`/system`) get a themed TOC at the top; keep TOC entries in sync with
  section IDs.
- **Markdown HARD rules (shared with the vault):** one blank line after
  frontmatter, never double blanks; no hard-wrapping mid-sentence (one line per
  paragraph) in `.md` drafts.

## 5. Writing → articles pipeline

- Drafts live in `W:/data/products/mdde/output/articles/drafts/` (PDR-067; O:
  dropped). Source of truth is the markdown; `build_articles.py` renders styled
  HTML.
- **Allow-list:** only stems listed in `ARTICLES` in `build_articles.py` publish —
  keeps unrelated/MDDE drafts private.
- **Frontmatter:** `title` (required), `subtitle`, `face` (`B2C…`/`B2B…` →
  audience label), `created`, optional `hero_image` + `hero_caption` (filename in
  `assets/`).
- **Do NOT** repeat the subtitle as an italic lede in the body — the builder
  renders the subtitle separately and now strips a leading `*italic*` lede, but
  don't rely on it; just omit the duplicate.
- **Figure shortcode:** `[[figure: filename.png | caption]]` — renders a captioned
  `figure.article-fig` from `assets/`. Subject to the image rule above (text
  between figures).
- Markdown subset supported: `#/##/###`, `**bold**` (may contain `*italic*`),
  `*italic*`, `[links](url)`, `---` rules, `-`/`*` bullet lists, figure shortcode.
- Rebuild after edits: `python build_articles.py` (writes `articles/*.html` +
  `_cards.html` for the homepage Writing strip).

## 6. SEO & metadata

- **Per page:** unique `<title>` (`Page — Structure Beats Magic`), `<meta
  name="description">` (~150 chars, benefit-led, no keyword stuffing), Open Graph
  (`og:title`, `og:description`, `og:type`, `og:image`) and `twitter:card =
  summary_large_image`.
- **og:image:** the page's hero (articles) or `assets/sbm-og-card.svg` (default).
- **Headings:** exactly one `<h1>` per page (the article/section title); real
  heading hierarchy, no skipped levels — it's read by both crawlers and AI.
- **Alt text on every image** — descriptive and specific (it's accessibility *and*
  SEO *and* what an LLM reads). Captions add context; alt describes the image.
- **Images:** `loading="lazy"` on everything except an above-the-fold hero
  (`loading="eager"`). Keep infographic PNGs reasonably sized.
- **Crawlability:** keep `robots.txt` + `sitemap.xml` current when pages are
  added; clean human-readable URLs (no query strings).
- **Internal links:** cross-link articles to each other, to `/system`, and the
  enterprise CTA to `jacovanderlaan.com` — a connected site is stronger for both
  readers and ranking. Outbound/affiliate-style links get `rel` as appropriate.
- **GitHub Pages base path:** templates prefix internal asset/photo URLs with a
  base helper where needed; keep `CNAME` correct for the custom domain.
- **Honesty = durable SEO.** No fabricated numbers, dates, or social proof.

## 7. Deploy

- Static host (GitHub Pages via Actions, or Netlify). No build command for the hub
  itself; `build_articles.py` is run locally before commit.
- Target domain `structurebeatsmagic.com` (DNS cutover at Dynadot — see
  `DOMAIN.md`). Interim: github.io / 301 to jacovanderlaan.com until cutover.
- Private assets (e.g. first-party venue photos in the travel sample) stay
  gitignored — never commit personal photos that aren't meant to publish.

### Asset hygiene — published-only repo (input vs publication)
- **Only assets referenced by the live site belong in `assets/`.** Unused images
  (unreferenced infographics, source photos, ChatGPT outputs you didn't place) do
  **not** live in this public repo.
- **Move, don't delete** unused images to the private staging area:
  `W:/data/products/mdde/output/articles/images/sbm-unused/` (see its README). They
  stay reproducible; the public repo stays clean and free of personal photos.
- Audit before committing: every file in `assets/` should be reachable by a
  `src=`/`url()` in some `.html`/`.css`. Anything else is an orphan — stage it out.
- The line: **publication is public (this repo), input/working is private** (the
  vault for prompts/drafts, the W: workspace for source images).
