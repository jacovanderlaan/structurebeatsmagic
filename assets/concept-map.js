
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
