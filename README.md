# Structure Beats Magic — hub site

The **master-brand landing site** for the *Structure Beats Magic* thesis:
Knowledge Management, re-architected for the AI era.

> The magic isn't in the model. It's in the structure you give it.
> **Structure + Data + AI + Rules + Skills → Systems.**

## Role in the brand architecture

This is the **umbrella hub**. It explains the universal principles, shows the two
implementations (personal + business), links to live sample systems, and routes
serious organisations onward to the enterprise consultancy.

```
structurebeatsmagic.com   ← THIS SITE (master / thesis hub)
  ├─ Universal principles   (the formula, free "recipe")
  ├─ Personal implementation (proof in the life: photos, books, trips)
  ├─ Business implementation (proof in the work: governed quality for mid-size
  │     orgs — "bankers vs builders")
  ├─ Sample systems          (live demos / write-ups)
  └─ → jacovanderlaan.com    (high-value enterprise consultancy — the cash lane)
```

It deliberately gives the **what/why** free and routes the **how/method** to paid
engagements ("give the recipe, sell the kitchen").

## Stack

Static-first per ADR-046: a single self-contained `index.html` (inline CSS, no
build step, no framework, no runtime). Matches the brand palette
(off-white / deep navy / blue accent / gold payoff) shared with jacovanderlaan.com.

## Preview

Open `index.html` directly, or serve the folder:

```bash
python -m http.server 8000   # then open http://localhost:8000
```

## Deploy

Any static host. Intended target: `structurebeatsmagic.com` (currently 301s to
jacovanderlaan.com as an interim; this site becomes the destination once wired).
GitHub Pages or Netlify both work — no build command, publish the repo root.

## Assets

`assets/` holds Jaco's own SBM brand graphics (hero / formula / toy-vs-instrument
/ og-card, as SVG), copied from the positioning brand-assets set.
