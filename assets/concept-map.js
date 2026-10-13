/* Neighbourhood / concept graph — ONE client for the whole family.
   Source: W:/systems/design/concept-map.js (with concept-map.css and graph_map.py).
   A site's builder copies it into <site>/assets/ (graph_map.install); never edit a site's copy.
   First used by structurebeatsmagic.com (concept map + per-concept mini-map, 21 Jul 2026),
   shared 13 Oct 2026 for deliberateway.com. Contract in design.md, "Neighbourhood graph".

   Container: <div class="cmap-wrap" data-src="<json id>" data-base="" data-h="380"
                   [data-hn="<height below data-narrow>"] [data-narrow="520"] [data-go="Open page">]<svg></svg></div>
   Data:      <script type="application/json" id="<json id>">{nodes, edges, categories?, center?}</script>
   Node:      {slug, title, cat?, desc?, url?, kind?, go?, minor?}
     url    optional. Absent: BASE + slug + '.html' (SBM). Absolute (http, //, /) used as is, else BASE + url.
            "" = not clickable.
     kind   optional, adds class k-<kind> (concept-map.css styles group, text, ext).
     go     optional tooltip action label; else data-go; else "Open concept".
     minor  optional, hidden while the container is narrower than data-narrow (default 520 px).
*/
(function(){
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function boot(root){
  const data = JSON.parse(document.getElementById(root.dataset.src).textContent);
  const BASE = root.dataset.base || "";
  const center = data.center || null;
  const NARROW = root.dataset.narrow ? +root.dataset.narrow : 520;
  const svg = root.querySelector('svg'), tip = document.querySelector('.cmap-tip')
        || Object.assign(document.body.appendChild(document.createElement('div')),{className:'cmap-tip'});
  function height(w){if(root.dataset.hn&&w<NARROW)return +root.dataset.hn;return root.dataset.h?+root.dataset.h:Math.max(420,Math.min(680,w*0.62));}
  let W = root.clientWidth, H = height(W);
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`); svg.style.height=H+'px';
  const NS='http://www.w3.org/2000/svg';
  const meas=document.createElementNS(NS,'text');meas.setAttribute('x',-9999);svg.appendChild(meas);
  function wrap(s,max){const w=s.split(' '),o=[];let c='';for(const x of w){if(c&&(c+' '+x).length>max){o.push(c);c=x;}else c=c?c+' '+x:x;}if(c)o.push(c);return o.slice(0,4);}
  function radius(lines,fp){meas.setAttribute('font-size',fp);meas.setAttribute('font-weight',700);let w=0;lines.forEach(l=>{meas.textContent=l;w=Math.max(w,meas.getComputedTextLength());});const h=lines.length*(fp+2);return Math.ceil(Math.hypot(w/2,h/2))+10;}
  function href(n){
    if(n.url==null) return BASE+n.slug+'.html';
    if(n.url==='') return '';
    return /^(https?:)?\/\/|^\//.test(n.url) ? n.url : BASE+n.url;
  }
  const vis=n=>!(n.minor&&W<NARROW);

  let N = data.nodes.map((n,i)=>({...n,i,x:W/2+(Math.random()-.5)*W*.5,y:H/2+(Math.random()-.5)*H*.5,vx:0,vy:0,center:n.slug===center,on:true}));
  N.forEach(n=>n.on=vis(n));
  const idx=Object.fromEntries(N.map(n=>[n.slug,n]));
  let E=data.edges.map(([a,b])=>({a:idx[a],b:idx[b]})).filter(e=>e.a&&e.b);
  N.forEach(n=>{const fp=n.center?14:12.5;n.lines=wrap(n.title,n.center?16:15);n.r=Math.max(n.center?42:26,radius(n.lines,fp));});

  const gE=document.createElementNS(NS,'g'),gN=document.createElementNS(NS,'g');svg.append(gE,gN);
  let edgeEls=[],nodeEls=[];
  function buildEls(){
    gE.innerHTML='';gN.innerHTML='';edgeEls=[];nodeEls=[];
    edgeEls=E.map(()=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','cmap-edge');gE.appendChild(l);return l;});
    nodeEls=N.map(n=>{
      const g=document.createElementNS(NS,'g');g.setAttribute('class','cmap-node'+(n.center?' center':'')+(n.kind?' k-'+n.kind:''));
      const c=document.createElementNS(NS,'circle');c.setAttribute('r',n.r);
      const fp=n.center?14:12.5,lh=fp+2,t=document.createElementNS(NS,'text');t.setAttribute('font-size',fp);
      n.lines.forEach((ln,k)=>{const ts=document.createElementNS(NS,'tspan');ts.textContent=ln;ts.setAttribute('x',0);ts.setAttribute('dy',k===0?(-(n.lines.length-1)*lh/2):lh);t.appendChild(ts);});
      g.append(c,t);gN.appendChild(g);
      const to=href(n);
      if(to){g.setAttribute('tabindex','0');g.setAttribute('role','link');g.setAttribute('aria-label',n.title);
        g.addEventListener('keydown',ev=>{if(ev.key==='Enter')location.href=to;});}
      else g.classList.add('nolink');
      g.addEventListener('click',()=>{if(!drag.moved&&to)location.href=to;});
      g.addEventListener('mouseenter',ev=>hover(n,ev));g.addEventListener('mousemove',moveTip);g.addEventListener('mouseleave',unhover);
      return g;});
  }
  buildEls();

  // One physics step. Split out of tick() (13 Oct 2026) so the layout can be
  // settled BEFORE the first paint: nodes start at random spots and move at most
  // 8px per step, so with 8+ large circles the first view showed them stacked.
  function settle(){
    for(const n of N){if(!n.on)continue;
      for(const m of N){if(n===m||!m.on)continue;let dx=n.x-m.x,dy=n.y-m.y,d=Math.hypot(dx,dy)||.1;const min=n.r+m.r+26;const f=min*min/(d*d)*2.2;n.vx+=dx/d*f;n.vy+=dy/d*f;if(d<min){const p=(min-d)*.5;n.vx+=dx/d*p;n.vy+=dy/d*p;}}}
    for(const e of E){if(!e.a.on||!e.b.on)continue;let dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,d=Math.hypot(dx,dy)||.1;const rest=e.a.r+e.b.r+70;const f=(d-rest)*.01;e.a.vx+=dx/d*f;e.a.vy+=dy/d*f;e.b.vx-=dx/d*f;e.b.vy-=dy/d*f;}
    for(const n of N){if(!n.on)continue;n.vx+=(W/2-n.x)*.0016;n.vy+=(H/2-n.y)*.0016;if(n===drag.node)continue;n.vx*=.86;n.vy*=.86;n.x+=Math.max(-8,Math.min(8,n.vx));n.y+=Math.max(-8,Math.min(8,n.vy));n.x=Math.max(n.r,Math.min(W-n.r,n.x));n.y=Math.max(n.r,Math.min(H-n.r,n.y));}
  }
  function tick(){
    settle();
    E.forEach((e,i)=>{const l=edgeEls[i];const v=e.a.on&&e.b.on;l.style.display=v?'':'none';if(v){l.setAttribute('x1',e.a.x);l.setAttribute('y1',e.a.y);l.setAttribute('x2',e.b.x);l.setAttribute('y2',e.b.y);}});
    N.forEach((n,i)=>{nodeEls[i].style.display=n.on?'':'none';if(n.on)nodeEls[i].setAttribute('transform',`translate(${n.x},${n.y})`);});
    requestAnimationFrame(tick);
  }
  function hover(n,ev){const nb=new Set([n.slug]);E.forEach(e=>{if(e.a.slug===n.slug)nb.add(e.b.slug);if(e.b.slug===n.slug)nb.add(e.a.slug);});
    N.forEach((m,i)=>nodeEls[i].classList.toggle('dim',m.on&&!nb.has(m.slug)));
    E.forEach((e,i)=>edgeEls[i].classList.toggle('hot',e.a.slug===n.slug||e.b.slug===n.slug));
    const go=href(n)?`<span class="go">${esc(n.go||root.dataset.go||'Open concept')} &rarr;</span>`:'';
    tip.innerHTML=`<b>${esc(n.title)}</b>${esc(n.desc||'')}${go}`;tip.style.opacity=1;moveTip(ev);}
  function moveTip(ev){let x=ev.clientX+12,y=ev.clientY+12;if(x+270>innerWidth)x=ev.clientX-270;if(y+110>innerHeight)y=ev.clientY-110;tip.style.left=x+'px';tip.style.top=y+'px';}
  function unhover(){N.forEach((m,i)=>nodeEls[i].classList.remove('dim'));E.forEach((e,i)=>edgeEls[i].classList.remove('hot'));tip.style.opacity=0;}

  const drag={node:null,moved:false};
  svg.addEventListener('pointerdown',ev=>{const g=ev.target.closest('.cmap-node');if(!g)return;drag.node=N[nodeEls.indexOf(g)];drag.moved=false;});
  svg.addEventListener('pointermove',ev=>{if(!drag.node)return;drag.moved=true;const r=svg.getBoundingClientRect();drag.node.x=(ev.clientX-r.left)/r.width*W;drag.node.y=(ev.clientY-r.top)/r.height*H;drag.node.vx=drag.node.vy=0;});
  addEventListener('pointerup',()=>setTimeout(()=>drag.node=null,0));
  addEventListener('resize',()=>{W=root.clientWidth;H=height(W);svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.style.height=H+'px';
    if(!filt)N.forEach(n=>{if(n.minor)n.on=vis(n);});});

  // category filters (full map only). Multi-select categories; the "All" chip
  // (empty data-cat) clears them. Opens focused on data-default-cat.
  const filt=root.querySelector('.cmap-filters');
  if(filt){
    function apply(){
      const active=[...filt.querySelectorAll('.cmap-chip.on')].map(c=>c.dataset.cat).filter(Boolean);
      N.forEach(n=>n.on = (active.length===0 || active.includes(n.cat)) && vis(n));
      filt.querySelector('.cmap-all')?.classList.toggle('on', active.length===0);
      // re-scatter the now-visible nodes so a filtered view spreads out
      N.forEach(n=>{ if(n.on){ n.x=W/2+(Math.random()-.5)*W*.4; n.y=H/2+(Math.random()-.5)*H*.4; } });
      for(let k=0;k<700;k++)settle(); // a filter click re-scatters: settle before the next paint too
    }
    filt.querySelectorAll('.cmap-chip').forEach(ch=>ch.addEventListener('click',()=>{
      if(ch.dataset.cat===''){ filt.querySelectorAll('.cmap-chip.on').forEach(c=>c.classList.remove('on')); }
      else ch.classList.toggle('on');
      apply();
    }));
    apply(); // honour the default-cat set in HTML
  }
  for(let k=0;k<700;k++)settle(); // lay out before the first paint, so nodes never start on top of each other
  tick();
}
document.querySelectorAll('.cmap-wrap').forEach(boot);
})();
