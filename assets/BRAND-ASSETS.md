# Structure Beats Magic — brand assets

Brand palette (from `article.css`): navy `#0f172a` · off-white `#f7f8fa` · accent-blue `#2563eb` · gold `#b88a1b`.
Source = SVG (edit + re-export). Medium/social need raster → PNG exports live beside each SVG.

## Publication avatar (Medium: square, ≥1000px, JPG/PNG/GIF — NOT SVG)
| File | Variant | Size | Use |
|---|---|---|---|
| `sbm-avatar.png` ⭐ | grid on navy | 1000×1000 | Default publication avatar. Shows as a circle. |
| `sbm-avatar-light.png` | grid on off-white | 1000×1000 | Light-background alternative. |
| `sbm-avatar-monogram.png` | "SBM" letters on navy | 1000×1000 | Use if you want the name legible in the circle. |

## Publication logo (Medium: name + transparent bg, ≥400px wide, JPG/PNG/GIF)
| File | Variant | Size | Use |
|---|---|---|---|
| `sbm-logo.png` ⭐ | mark + 2-line wordmark, transparent | 1200×320 | Default publication logo (top of publication). |
| `sbm-logo-inline.png` | mark + 1-line wordmark, transparent | 1600×220 | Wide/header placement. |

## Concept: the mark
An ordered grid of blocks — calm navy/blue/grey — with ONE **gold** block: the payoff that structure earns. "Structure (order) beats magic (the lone lucky-looking highlight is actually earned)." Wordmark: Georgia serif, "Magic" in gold.

## Other existing brand SVGs (thesis graphics, not avatar/logo)
- `sbm-hero.svg` · `sbm-formula.svg` (`Structure + Data + AI + Rules + Skills → Systems`) · `sbm-og-card.svg` (social share) · `sbm-toy-vs-instrument.svg`.

## Re-export (SVG → PNG)
No CLI SVG→PNG converter is installed; use Python `cairosvg` (works in this env):
```python
import cairosvg
cairosvg.svg2png(url="sbm-avatar.svg", write_to="sbm-avatar.png",
                 output_width=1000, output_height=1000)
```
Logo transparency: keep it — the SVGs have no background rect (colortype RGBA in the PNG).

> ⚠️ Medium does NOT accept SVG uploads (JPG/PNG/GIF only). Always upload the `.png`.
> Vault cross-ref: `D:/vault/personal/career/2-active/positioning/2026-07-01_sbm-publication-description.md`
