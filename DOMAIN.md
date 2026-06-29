# Custom domain — structurebeatsmagic.com (NOT yet wired)

The custom domain is intentionally **NOT active** right now, so the
`github.io/structurebeatsmagic/` URL serves this site directly for preview
(GitHub auto-redirects github.io → custom domain whenever one is set).

## To go live on the domain (cutover)

1. Re-add a `CNAME` file at repo root containing: `structurebeatsmagic.com`
   (or set it in repo Settings → Pages → Custom domain).
2. In **Dynadot**: remove the 301 forwarding, then point DNS to GitHub Pages:
   - apex `A` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `www` `CNAME` → `jacovanderlaan.github.io`
3. GitHub verifies the domain + issues SSL automatically.

This enacts the "redirect → hub" promotion (SBM as master brand).
