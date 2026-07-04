# Image catalog — structurebeatsmagic.com

> Zelf-documenterend overzicht van de artikel-infographics. Naamconventie:
> **`<article-slug>-<rol>.png`** (rol = `hero` voor de openings-image, dan `01`, `02`, …
> op volgorde van voorkomen in het artikel). Nooit UUID-namen — die zijn onvindbaar.
> Bijgewerkt: 2026-07-01 (bulk-rename van 20 UUID-images).

## Naamconventie (VERPLICHT)
- `hero` = eerste/openings-image van het artikel.
- `01`, `02`, … = volgende images, in leesvolgorde.
- Slug = de artikel-bestandsnaam zonder `.html` (index → `home`).
- **Bij generatie meteen zo benoemen** — geen UUID's laten staan.

## Per artikel

### why-structure-beats-magic
- `why-structure-beats-magic-hero.png` — "A System You Can Count On" (person aan bureau kijkt uit op een pad; links de magie-kant boeken STORIES/MUSIC/AI + hoed/gitaar/luck/genius/hope, rechts whiteboard capture→organise→retrieve→use + PLAN/HABITS/SYSTEMS/RESULTS; onderbalk stories/music/AI/focus/system/results)

### a-brain-that-publishes-itself
- `a-brain-that-publishes-itself-hero.png` — "Built on Structure. Driven by Insight. Outputs That Multiply." (closed-loop content-systeem: capture→structure→AI→publish→learn)
- `a-brain-that-publishes-itself-01.png` — "The Publishing Engine" (ideas→knowledge graph→templates→AI→content→formats: newsletter/LinkedIn/blog/book/podcast)
- `a-brain-that-publishes-itself-02.png` — brain met inputs (experiences/ideas/notes/reading/data) → outputs (article/blog/ebook/framework/diagrams)

### home (index.html)
- `home-hero.png` — "The Difference Between Memory and Knowledge" (memory = losse post-its vs knowledge = verbonden graph; "structure turns scattered pieces into a system that thinks")

### stop-prompting-start-directing
- `stop-prompting-start-directing-hero.png` — "The North Star: Direction Over Speed" (kompas; without vs with direction; direction = de multiplier)
- `stop-prompting-start-directing-01.png` — "The 5 Dimensions of Direction Quality" (clarity/alignment/focus/actionability/impact + score-guides 0-100)

### your-bookshelf-is-already-a-knowledge-base
- `...-hero.png` t/m `...-05.png` — 6 images (bookshelf → knowledge-base thema)

### your-trips-are-already-structured-data-part-1
- `...-hero.png` t/m `...-05.png` — 6 images. O.a. "Your Timeline Is Already Structured" (Madeira-trip als sequence: book→fly→hotel→activities→…→home)

### your-trips-are-already-structured-data-part-2
- `...-hero.png` — "One System. Your Complete Travel Knowledge" (data in → knowledge graph → insights → better trips; DEMO-cijfers, "Illustrative")
- `...-01.png` — 2e trips-part-2 image

### the-filter-youre-missing-anti-interests
- `...-hero.png` — "Key Takeaways: Anti-Interests in Action" (drains → filter → fuels; wat je wint; daily checklist; voorbeelden)
- `...-01.png` — "Anti-Interests Cheat Sheet" (Filter → Focus → Conserve → Progress → Review)
- `...-02.png` — "Common Mistakes (and How to Avoid Them)" (No-as-wall vs No-as-filter)
- `...-03.png` — "Your Anti-Interests Worksheet" (5 stappen + 10-regel lijst-template)
- `...-04.png` — "Your 30-Day Anti-Interests Action Plan" (week 1-4: discover/apply/protect/refine)

## ⚠️ Status per 2026-07-01
- Alle infographics zijn gekoppeld aan een artikel (0 orphans).
- Anti-interests-artikel: 5 images geplaatst (hero + 4 inline), IMAGE RULE OK (geverifieerd).
- Bij nieuwe images: hernoem meteen naar `<slug>-<rol>.png`, plaats per IMAGE RULE, en voeg hier een regel toe. Audit: `ls assets/*.png | grep -E '[0-9a-f]{8}-[0-9a-f]{4}'` moet leeg zijn.
