/* Confere os números novos da página contra o próprio modelo:
 * soma dos estados = total, regiões = soma dos estados, estimativa por
 * município coerente com a projeção, e que nada disso mexeu na projeção. */
import { readFileSync } from "node:fs";
import { Modelo } from "../modelo.js";
const raiz = new URL("../", import.meta.url);
const ler = (n) => JSON.parse(readFileSync(new URL(n, raiz)));
const base = ler("base.json"), ordem = ler("ordem.json");
const m = new Modelo(base);
const idx = new Map(); base.ufs.forEach((u, i) => idx.set(u + "/" + base.cds[i], i));
const total = base.ele.reduce((a, b) => a + b, 0);
let falhas = 0;
const ok = (c, t) => { console.log((c ? "  ok   " : "  FALHA ") + t); if (!c) falhas++; };
for (const pct of [0, 1, 5, 10, 25, 50, 90, 100]) {
  const fr = new Map(), ob = {}; let ac = 0;
  for (const k of ordem) { if (ac >= pct / 100 * total) break; const i = idx.get(k); if (i === undefined) continue;
    fr.set(k, 1); const u = base.ufs[i]; ob[u] = ob[u] || { pl: 0, pt: 0 }; ob[u].pl += base.pl[i]; ob[u].pt += base.pt[i]; ac += base.ele[i]; }
  const r = m.projetar(fr, ob, 100);
  const sPl = r.estados.reduce((a, e) => a + e.vPl, 0), sPt = r.estados.reduce((a, e) => a + e.vPt, 0);
  ok(Math.abs(sPl - r.totalPl) < 1 && Math.abs(sPt - r.totalPt) < 1, `${pct}%: soma dos estados = total projetado`);
  ok(Math.abs(100 * r.totalPl / (r.totalPl + r.totalPt) - r.projecaoPl) < 1e-9, `${pct}%: total projetado bate com a % da projeção (${r.projecaoPl.toFixed(3)})`);
  for (const e of r.estados) if (Math.abs(100 * e.vPl / (e.vPl + e.vPt) - e.projPl) > 1e-9) { ok(false, `${pct}%: ${e.uf} vPl/vPt incoerente`); }
  // estimativa municipal: o que falta somado com ela = projeção do estado (sem escala de votos)
  const est = m.estimarMunicipios();
  let maxd = 0;
  for (const [uf, ids] of m.indicesPorUf) {
    const o = ob[uf] || { pl: 0, pt: 0 }; let pl = o.pl, pt = o.pt;
    const e = r.estados.find((x) => x.uf === uf.toUpperCase());
    // reconstrói o _somar com a mesma escala que o modelo usou: compara só a parte que falta
    let fpl = 0, fpt = 0;
    for (const i of ids) { const f = 1 - m.fracao[i]; fpl += f * m.validosBase[i] * est[i] / 100; fpt += f * m.validosBase[i] * (1 - est[i] / 100); }
    const restoModelo = e.vPl + e.vPt - pl - pt;
    if (restoModelo > 1000 && fpl + fpt > 0) {
      const d = Math.abs(100 * fpl / (fpl + fpt) - 100 * (e.vPl - pl) / restoModelo);
      maxd = Math.max(maxd, d);
    }
  }
  ok(maxd < 1e-6, `${pct}%: estimativa por município reproduz o que falta de cada estado (desvio máx ${maxd.toExponential(1)} pp)`);
  ok(est.every((v) => v >= 0 && v <= 100), `${pct}%: estimativas municipais entre 0 e 100`);
}
console.log(falhas ? `\n${falhas} falha(s)` : "\ntudo coerente");
process.exit(falhas ? 1 : 0);
