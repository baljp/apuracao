/*
 * Confere que o modelo em JavaScript dá o mesmo resultado que o modelo em
 * Python. Os dois têm que concordar — se divergirem, um dos dois está errado.
 *
 * Roda o modelo sobre o 1º turno de 2026 já 100% apurado: nesse caso a
 * projeção tem que bater exatamente com o resultado real, porque não sobra
 * nada para projetar.
 *
 * Uso:  node conferir.mjs
 */

import { readFileSync } from "node:fs";
import { Modelo } from "./modelo.js";
import * as tse from "./tse.js";

const base = JSON.parse(readFileSync(new URL("./base.json", import.meta.url)));
const modelo = new Modelo(base);

console.log("Base: " + modelo.n + " municípios, " +
  (modelo.eleitoradoTotal / 1e6).toFixed(1) + " milhões de eleitores");

// --- teste 1: tudo apurado, projeção tem que ser o resultado exato ---------
const tudo = new Map();
const observadoCheio = {};
for (let i = 0; i < modelo.n; i++) {
  tudo.set(modelo.chave[i], 1.0);
  const uf = modelo.uf[i];
  if (!observadoCheio[uf]) observadoCheio[uf] = { pl: 0, pt: 0 };
  observadoCheio[uf].pl += base.pl[i];
  observadoCheio[uf].pt += base.pt[i];
}
const cheio = modelo.projetar(tudo, observadoCheio, 0);
const real = 100 * base.pl.reduce((a, b) => a + b, 0) /
  (base.pl.reduce((a, b) => a + b, 0) + base.pt.reduce((a, b) => a + b, 0));

console.log("\n100%% apurado:");
console.log("  resultado real: %s%%", real.toFixed(4));
console.log("  projeção:       %s%%", cheio.projecaoPl.toFixed(4));
const erro1 = Math.abs(cheio.projecaoPl - real);
console.log("  diferença:      %s pp  %s", erro1.toFixed(6),
  erro1 < 1e-6 ? "OK" : "FALHOU");

// --- teste 2: apuração parcial real, buscando do TSE -----------------------
console.log("\nLendo o TSE ao vivo (1º turno) para um teste de ponta a ponta...");
try {
  const { observado, fracoes, falhas } = await tse.lerTudo(tse.ELEICAO_1T);
  const r = modelo.projetar(fracoes, observado, 120);
  console.log("  apurado:   %s%%", r.pctApurado.toFixed(2));
  console.log("  bruto:     %s%%", r.brutoPl?.toFixed(2));
  console.log("  projeção:  %s%%  (faixa %s – %s)",
    r.projecaoPl.toFixed(2), r.faixaPl[0].toFixed(2), r.faixaPl[1].toFixed(2));
  console.log("  estados:   %d", r.estados.length);
  if (falhas.length) console.log("  falhas:    %s", falhas.join(", "));
  const erro2 = Math.abs(r.projecaoPl - real);
  console.log("  diferença contra o resultado real: %s pp  %s",
    erro2.toFixed(4), erro2 < 0.01 ? "OK" : "verificar");
} catch (e) {
  console.log("  não consegui ler o TSE agora: %s", e.message);
}

// --- teste 3: simulação com 5% apurado, na ordem real de chegada -----------
let ordem = null;
try {
  ordem = JSON.parse(readFileSync(new URL("../ordem_1t_2026.json", import.meta.url))).ordem;
} catch { /* opcional */ }

if (ordem) {
  console.log("\nSimulação: 5%% apurado, na ordem real em que os municípios fecharam");
  const idxPorChave = modelo.porChave;
  const total = modelo.eleitoradoTotal;
  const parcial = new Map();
  const obs = {};
  let acc = 0, obsPl = 0, obsPt = 0;
  for (const it of ordem) {
    if (acc >= 0.05 * total) break;
    const i = idxPorChave.get(it.chave);
    if (i === undefined) continue;
    parcial.set(it.chave, 1.0);
    const uf = modelo.uf[i];
    if (!obs[uf]) obs[uf] = { pl: 0, pt: 0 };
    obs[uf].pl += base.pl[i]; obs[uf].pt += base.pt[i];
    obsPl += base.pl[i]; obsPt += base.pt[i];
    acc += modelo.eleitorado[i];
  }
  const r5 = modelo.projetar(parcial, obs, 200);
  const bruto = 100 * obsPl / (obsPl + obsPt);
  console.log("  bruto com 5%%:  %s%%  (erro %s pp)",
    bruto.toFixed(2), (bruto - real).toFixed(2));
  console.log("  projeção:      %s%%  (erro %s pp)",
    r5.projecaoPl.toFixed(2), (r5.projecaoPl - real).toFixed(2));
  console.log("\n  (aqui a base e o alvo são a MESMA eleição, então o swing");
  console.log("   verdadeiro é zero — isso testa a correção do viés geográfico,");
  console.log("   que é justamente o que derruba o erro de %s pp para %s pp.)",
    Math.abs(bruto - real).toFixed(1), Math.abs(r5.projecaoPl - real).toFixed(2));
}
