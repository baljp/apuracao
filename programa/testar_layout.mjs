/* Procura texto cortado, número vazando e rolagem horizontal em 8 larguras de tela (320 a 1440 px). Uso: python3 -m http.server 8899 & node programa/testar_layout.mjs */
import puppeteer from "puppeteer-core";
const b=await puppeteer.launch({executablePath:"/root/.cache/puppeteer/chrome/linux-131.0.6778.204/chrome-linux64/chrome",args:["--no-sandbox"]});
const larguras=(process.env.LARG||"320,360,375,390,414,768,1024,1440").split(",").map(Number);
const urls=[["?demo=40","apuracao"],["?demo=40","cards"],["","apuracao"],["","pesquisas"]];
for (const [u,aba] of urls) for (const w of larguras) {
  const p=await b.newPage();await p.setViewport({width:w,height:900});
  p.on('pageerror',e=>console.log('PAGEERR',w,u,e.message));
  await p.goto("http://localhost:8899/"+u,{waitUntil:"networkidle0",timeout:60000});
  await new Promise(r=>setTimeout(r,u?5000:3000));
  if (aba!=="apuracao") { await p.evaluate((a)=>document.querySelector(`[data-aba=${a}]`).click(),aba); await new Promise(r=>setTimeout(r,2500)); }
  const res=await p.evaluate(()=>{
    const W=document.documentElement.clientWidth, out=[];
    if (document.documentElement.scrollWidth>W+1) out.push('PAGINA rola na horizontal: '+document.documentElement.scrollWidth);
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('[hidden],.atalhos,svg,.stories,.cardModal')) continue;
      const cs=getComputedStyle(el); if (cs.display==='none'||cs.visibility==='hidden') continue;
      const r=el.getBoundingClientRect(); if(!r.width) continue;
      if (r.right>W+1 || r.left<-1) out.push('fora: '+el.tagName+'.'+el.className+' #'+el.id+' '+Math.round(r.left)+'-'+Math.round(r.right)+' "'+(el.textContent||'').trim().slice(0,30)+'"');
      if (el.children.length===0 && el.scrollWidth>el.clientWidth+1 && cs.overflow!=='visible' ) out.push('cortado: '+el.tagName+'.'+el.className+' #'+el.id+' "'+el.textContent.trim().slice(0,30)+'"');
      // texto de um irmão invadindo o outro no placar
    }
    const a=document.getElementById('pctPL'),b=document.getElementById('pctPT');
    for (const sel of ['#pctPL','#pctPT','#previaPesquisas .pct','#pPctPL','#pPctPT']) for (const e of document.querySelectorAll(sel)) {
      const r=e.getBoundingClientRect(); if(!r.width) continue;
      const rng=document.createRange();rng.selectNodeContents(e);const t=rng.getBoundingClientRect();
      const box=e.parentElement.getBoundingClientRect();
      if (t.right>box.right+1||t.left<box.left-1) out.push('NUMERO vaza: '+sel+' '+e.textContent+' texto '+Math.round(t.left)+'-'+Math.round(t.right)+' caixa '+Math.round(box.left)+'-'+Math.round(box.right));
    }
    return [...new Set(out)].slice(0,12);
  });
  if (res.length) console.log(`== ${w}px ${u||'(inicio)'} ${aba}\n  `+res.join('\n  '));
  await p.close();
}
await b.close();
console.log('fim');
