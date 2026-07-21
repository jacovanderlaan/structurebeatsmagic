"""Concept mind-map: the graph data + the shared client for both surfaces.

Two surfaces, one engine (Jaco's request, 2026-07-21):
  1. a full /map/ page — every concept, filterable by category
  2. a mini-map at the bottom of each concept page — that concept's neighbourhood

Both are fed the same JSON (built here from the parsed Concept objects) and
rendered by the same force-directed client (graph_client_js). The builder owns
this: nothing drifts as a hand-edited HTML file, because the map is regenerated
from the concept frontmatter on every build. "A brain that publishes itself,"
applied to the concept map.

Circles are sized to fit their LABEL (measured in the browser), not their degree
-- degree-sizing made long titles overflow the ring (fixed 2026-07-21).
"""

from __future__ import annotations

import html
import json


def build_graph(concepts) -> dict:
    """Whole-library graph: nodes (with category) + de-duplicated edges.

    `concepts` is the list of parsed Concept objects. related_concepts holds
    slugs or names; we resolve both to slugs and drop any edge whose target has
    no page, so the map never links to a 404 (same rule as the page renderer).
    """
    by_slug = {c.slug: c for c in concepts}
    by_name = {c.name.lower(): c for c in concepts}

    def resolve(ref: str) -> str | None:
        r = ref.strip()
        if r.startswith("concept-"):
            r = r[len("concept-"):]
        if r in by_slug:
            return r
        c = by_name.get(ref.strip().lower())
        return c.slug if c else None

    nodes = [{
        "slug": c.slug,
        "title": c.name,
        "cat": c.category or "",
        "desc": (c.tag or "")[:150],
    } for c in sorted(concepts, key=lambda c: c.name.lower())]

    seen = set()
    edges = []
    for c in concepts:
        for ref in c.related_concepts:
            t = resolve(ref)
            if not t or t == c.slug:
                continue
            key = tuple(sorted((c.slug, t)))
            if key in seen:
                continue
            seen.add(key)
            edges.append(list(key))

    cats = []
    for c in nodes:
        if c["cat"] and c["cat"] not in cats:
            cats.append(c["cat"])

    return {"nodes": nodes, "edges": edges, "categories": cats}


def neighbourhood(graph: dict, center: str, hops: int = 1) -> dict:
    """The sub-graph around one concept, out to `hops` steps — for the mini-map."""
    adj: dict[str, set] = {}
    for a, b in graph["edges"]:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    keep = {center}
    frontier = {center}
    for _ in range(hops):
        nxt = set()
        for n in frontier:
            nxt |= adj.get(n, set())
        keep |= nxt
        frontier = nxt
    nodes = [n for n in graph["nodes"] if n["slug"] in keep]
    edges = [e for e in graph["edges"] if e[0] in keep and e[1] in keep]
    return {"nodes": nodes, "edges": edges,
            "categories": graph["categories"], "center": center}


# --------------------------------------------------------------------------- #
# Client — shared by both surfaces. Pure vanilla JS + inline SVG, CSP-safe.    #
# --------------------------------------------------------------------------- #

GRAPH_CSS = """
.cmap-wrap{position:relative;width:100%;background:var(--bg,#f7f8fa);
  border:1px solid var(--line,#e2e8f0);border-radius:16px;overflow:hidden}
.cmap-wrap svg{display:block;width:100%;cursor:grab;touch-action:none}
.cmap-wrap svg:active{cursor:grabbing}
.cmap-edge{stroke:var(--line,#e2e8f0);stroke-width:1.4;transition:stroke .15s,stroke-width .15s}
.cmap-edge.hot{stroke:var(--accent,#2563eb);stroke-width:2.2}
.cmap-node{cursor:pointer}
.cmap-node circle{fill:#fff;stroke:var(--accent,#2563eb);stroke-width:1.6;transition:stroke-width .15s,filter .15s}
.cmap-node text{fill:var(--ink,#0f172a);font-size:12.5px;font-weight:600;pointer-events:none;text-anchor:middle}
.cmap-node.center circle{fill:#fff7e6;stroke:var(--gold,#b88a1b);stroke-width:2.6}
.cmap-node.center text{font-weight:800}
.cmap-node.dim{opacity:.26}
.cmap-node:hover circle{stroke-width:3;filter:drop-shadow(0 3px 8px rgba(37,99,235,.25))}
.cmap-tip{position:fixed;pointer-events:none;background:#fff;border:1px solid var(--line,#e2e8f0);
  border-radius:10px;padding:9px 12px;max-width:260px;box-shadow:0 8px 24px rgba(15,23,42,.14);
  font-size:.84rem;color:var(--ink-soft,#475569);opacity:0;transition:opacity .12s;z-index:60;line-height:1.4}
.cmap-tip b{color:var(--ink,#0f172a);display:block;margin-bottom:2px;font-size:.92rem}
.cmap-tip .go{color:var(--accent,#2563eb);font-weight:600;margin-top:5px;display:block;font-size:.78rem}
.cmap-filters{display:flex;flex-wrap:wrap;gap:.5rem;padding:.9rem 1rem;border-bottom:1px solid var(--line,#e2e8f0)}
.cmap-chip{font-size:.8rem;font-weight:600;padding:.3rem .7rem;border-radius:999px;cursor:pointer;
  border:1px solid var(--line,#e2e8f0);background:#fff;color:var(--ink-soft,#475569);transition:all .12s}
.cmap-chip.on{background:var(--accent,#2563eb);border-color:var(--accent,#2563eb);color:#fff}
@media (prefers-color-scheme:dark){
  .cmap-wrap{background:#0f172a;border-color:#334155}
  .cmap-node circle{fill:#1e293b;stroke:#60a5fa}
  .cmap-node.center circle{fill:#3a2f12;stroke:#d4a53a}
  .cmap-node text{fill:#e2e8f0}
  .cmap-tip,.cmap-chip{background:#1e293b;border-color:#334155;color:#94a3b8}
  .cmap-tip b{color:#e2e8f0}
  .cmap-filters{border-color:#334155}
}
"""

# The client reads a <script type="application/json" id="{id}-data"> block and a
# few data-attrs on the container, so one function serves both surfaces.
GRAPH_JS = r"""
(function(){
function boot(root){
  const data = JSON.parse(document.getElementById(root.dataset.src).textContent);
  const BASE = root.dataset.base || "";
  const center = data.center || null;
  const svg = root.querySelector('svg'), tip = document.querySelector('.cmap-tip')
        || Object.assign(document.body.appendChild(document.createElement('div')),{className:'cmap-tip'});
  let W = root.clientWidth, H = root.dataset.h ? +root.dataset.h : Math.max(420, Math.min(680, root.clientWidth*0.62));
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`); svg.style.height=H+'px';
  const NS='http://www.w3.org/2000/svg';
  const meas=document.createElementNS(NS,'text');meas.setAttribute('x',-9999);svg.appendChild(meas);
  function wrap(s,max){const w=s.split(' '),o=[];let c='';for(const x of w){if(c&&(c+' '+x).length>max){o.push(c);c=x;}else c=c?c+' '+x:x;}if(c)o.push(c);return o.slice(0,4);}
  function radius(lines,fp){meas.setAttribute('font-size',fp);meas.setAttribute('font-weight',700);let w=0;lines.forEach(l=>{meas.textContent=l;w=Math.max(w,meas.getComputedTextLength());});const h=lines.length*(fp+2);return Math.ceil(Math.hypot(w/2,h/2))+10;}

  let N = data.nodes.map((n,i)=>({...n,i,x:W/2+(Math.random()-.5)*W*.5,y:H/2+(Math.random()-.5)*H*.5,vx:0,vy:0,center:n.slug===center,on:true}));
  const idx=Object.fromEntries(N.map(n=>[n.slug,n]));
  let E=data.edges.map(([a,b])=>({a:idx[a],b:idx[b]})).filter(e=>e.a&&e.b);
  N.forEach(n=>{const fp=n.center?14:12.5;n.lines=wrap(n.title,n.center?16:15);n.r=Math.max(n.center?42:26,radius(n.lines,fp));});

  const gE=document.createElementNS(NS,'g'),gN=document.createElementNS(NS,'g');svg.append(gE,gN);
  let edgeEls=[],nodeEls=[];
  function buildEls(){
    gE.innerHTML='';gN.innerHTML='';edgeEls=[];nodeEls=[];
    edgeEls=E.map(()=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','cmap-edge');gE.appendChild(l);return l;});
    nodeEls=N.map(n=>{
      const g=document.createElementNS(NS,'g');g.setAttribute('class','cmap-node'+(n.center?' center':''));
      const c=document.createElementNS(NS,'circle');c.setAttribute('r',n.r);
      const fp=n.center?14:12.5,lh=fp+2,t=document.createElementNS(NS,'text');t.setAttribute('font-size',fp);
      n.lines.forEach((ln,k)=>{const ts=document.createElementNS(NS,'tspan');ts.textContent=ln;ts.setAttribute('x',0);ts.setAttribute('dy',k===0?(-(n.lines.length-1)*lh/2):lh);t.appendChild(ts);});
      g.append(c,t);gN.appendChild(g);
      g.addEventListener('click',()=>{if(!drag.moved&&BASE!==null)location.href=BASE+n.slug+'.html';});
      g.addEventListener('mouseenter',ev=>hover(n,ev));g.addEventListener('mousemove',moveTip);g.addEventListener('mouseleave',unhover);
      return g;});
  }
  buildEls();

  function tick(){
    for(const n of N){if(!n.on)continue;
      for(const m of N){if(n===m||!m.on)continue;let dx=n.x-m.x,dy=n.y-m.y,d=Math.hypot(dx,dy)||.1;const min=n.r+m.r+26;const f=min*min/(d*d)*2.2;n.vx+=dx/d*f;n.vy+=dy/d*f;if(d<min){const p=(min-d)*.5;n.vx+=dx/d*p;n.vy+=dy/d*p;}}}
    for(const e of E){if(!e.a.on||!e.b.on)continue;let dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,d=Math.hypot(dx,dy)||.1;const rest=e.a.r+e.b.r+70;const f=(d-rest)*.01;e.a.vx+=dx/d*f;e.a.vy+=dy/d*f;e.b.vx-=dx/d*f;e.b.vy-=dy/d*f;}
    for(const n of N){if(!n.on)continue;n.vx+=(W/2-n.x)*.0016;n.vy+=(H/2-n.y)*.0016;if(n===drag.node)continue;n.vx*=.86;n.vy*=.86;n.x+=Math.max(-8,Math.min(8,n.vx));n.y+=Math.max(-8,Math.min(8,n.vy));n.x=Math.max(n.r,Math.min(W-n.r,n.x));n.y=Math.max(n.r,Math.min(H-n.r,n.y));}
    E.forEach((e,i)=>{const l=edgeEls[i];const v=e.a.on&&e.b.on;l.style.display=v?'':'none';if(v){l.setAttribute('x1',e.a.x);l.setAttribute('y1',e.a.y);l.setAttribute('x2',e.b.x);l.setAttribute('y2',e.b.y);}});
    N.forEach((n,i)=>{nodeEls[i].style.display=n.on?'':'none';if(n.on)nodeEls[i].setAttribute('transform',`translate(${n.x},${n.y})`);});
    requestAnimationFrame(tick);
  }
  function hover(n,ev){const nb=new Set([n.slug]);E.forEach(e=>{if(e.a.slug===n.slug)nb.add(e.b.slug);if(e.b.slug===n.slug)nb.add(e.a.slug);});
    N.forEach((m,i)=>nodeEls[i].classList.toggle('dim',m.on&&!nb.has(m.slug)));
    E.forEach((e,i)=>edgeEls[i].classList.toggle('hot',e.a.slug===n.slug||e.b.slug===n.slug));
    tip.innerHTML=`<b>${n.title}</b>${n.desc||''}<span class="go">Open concept &rarr;</span>`;tip.style.opacity=1;moveTip(ev);}
  function moveTip(ev){let x=ev.clientX+12,y=ev.clientY+12;if(x+270>innerWidth)x=ev.clientX-270;if(y+110>innerHeight)y=ev.clientY-110;tip.style.left=x+'px';tip.style.top=y+'px';}
  function unhover(){N.forEach((m,i)=>nodeEls[i].classList.remove('dim'));E.forEach((e,i)=>edgeEls[i].classList.remove('hot'));tip.style.opacity=0;}

  const drag={node:null,moved:false};
  svg.addEventListener('pointerdown',ev=>{const g=ev.target.closest('.cmap-node');if(!g)return;drag.node=N[nodeEls.indexOf(g)];drag.moved=false;});
  svg.addEventListener('pointermove',ev=>{if(!drag.node)return;drag.moved=true;const r=svg.getBoundingClientRect();drag.node.x=(ev.clientX-r.left)/r.width*W;drag.node.y=(ev.clientY-r.top)/r.height*H;drag.node.vx=drag.node.vy=0;});
  addEventListener('pointerup',()=>setTimeout(()=>drag.node=null,0));
  addEventListener('resize',()=>{W=root.clientWidth;H=root.dataset.h?+root.dataset.h:Math.max(420,Math.min(680,root.clientWidth*0.62));svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.style.height=H+'px';});

  // category filters (full map only). Multi-select categories; the "All" chip
  // (empty data-cat) clears them. Opens focused on data-default-cat.
  const filt=root.querySelector('.cmap-filters');
  if(filt){
    function apply(){
      const active=[...filt.querySelectorAll('.cmap-chip.on')].map(c=>c.dataset.cat).filter(Boolean);
      N.forEach(n=>n.on = active.length===0 || active.includes(n.cat));
      filt.querySelector('.cmap-all')?.classList.toggle('on', active.length===0);
      // re-scatter the now-visible nodes so a filtered view spreads out
      N.forEach(n=>{ if(n.on){ n.x=W/2+(Math.random()-.5)*W*.4; n.y=H/2+(Math.random()-.5)*H*.4; } });
    }
    filt.querySelectorAll('.cmap-chip').forEach(ch=>ch.addEventListener('click',()=>{
      if(ch.dataset.cat===''){ filt.querySelectorAll('.cmap-chip.on').forEach(c=>c.classList.remove('on')); }
      else ch.classList.toggle('on');
      apply();
    }));
    apply(); // honour the default-cat set in HTML
  }
  tick();
}
document.querySelectorAll('.cmap-wrap').forEach(boot);
})();
"""


def graph_json_script(graph: dict, elem_id: str) -> str:
    """The data block the client reads. JSON in a script tag = CSP-safe, no eval."""
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
    return f'<script type="application/json" id="{elem_id}">{payload}</script>'


def full_map_container(graph: dict, base: str, default_cat: str = "") -> str:
    """The interactive container for the /map/ page: filters + svg + data.

    Opens focused on one category (default_cat) rather than showing all 118
    nodes at once, which was an unreadable cloud. An "All concepts" chip clears
    the filter. (2026-07-21, Jaco's call.)
    """
    cats = graph["categories"]
    if default_cat not in cats:
        # fall back to the smallest sensible starting cluster
        default_cat = "Personal data model" if "Personal data model" in cats else cats[0]
    chips = ['<button class="cmap-chip cmap-all" data-cat="">All concepts</button>']
    for c in cats:
        on = " on" if c == default_cat else ""
        chips.append(
            f'<button class="cmap-chip{on}" data-cat="{html.escape(c)}">{html.escape(c)}</button>')
    return (
        f'<div class="cmap-wrap" data-src="cmap-full-data" data-base="{html.escape(base)}"'
        f' data-h="900" data-default-cat="{html.escape(default_cat)}">'
        f'<div class="cmap-filters">{"".join(chips)}</div><svg></svg></div>'
        + graph_json_script(graph, "cmap-full-data")
    )


def mini_map_container(graph: dict, center: str, base: str) -> str:
    """The neighbourhood container for a concept detail page (no filters)."""
    sub = neighbourhood(graph, center, hops=1)
    if len(sub["nodes"]) < 3:
        return ""  # nothing worth drawing for an isolated concept
    return (
        f'<div class="cmap-wrap" data-src="cmap-mini-data" data-base="{html.escape(base)}" data-h="380">'
        f'<svg></svg></div>'
        + graph_json_script(sub, "cmap-mini-data")
    )
