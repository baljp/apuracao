/*
 * Bateria de testes do site, rodando fora do navegador.
 *
 * Checa as peças que o visitante vê: o modelo em vários pontos da apuração,
 * o mapa, as pesquisas e a leitura ao vivo do TSE. Cada bloco roda várias
 * vezes, porque erro que só aparece de vez em quando é o pior tipo de erro
 * numa noite de apuração — e porque a leitura do TSE depende de rede.
 *
 * Uso:  node programa/testar_site.mjs [repeticoes]
 */

import { readFileSync } from "node:fs";

/* O site lê a tabela da Wikipédia com DOMParser, que é do navegador. Para
 * testar a mesma função aqui fora, basta oferecer um equivalente. */
if (typeof globalThis.DOMParser === "undefined") {
  try {
    const { DOMParser } = await import("linkedom");
    globalThis.DOMParser = DOMParser;
  } catch {
    console.log("(sem linkedom: o bloco de pesquisas vai falhar — "
      + "rode `npm install --no-save linkedom`)");
  }
}
import { Modelo } from "../modelo.js";
import * as tse from "../tse.js";
import * as pq from "../pesquisas.js";

const REPS = parseInt(process.argv[2] || "5", 10);
const raiz = new URL("../", import.meta.url);
const ler = (n) => JSON.parse(readFileSync(new URL(n, raiz)));

let falhas = 0;
const ok = (cond, texto, detalhe = "") => {
  console.log(`  ${cond ? "ok  " : "FALHA"}  ${texto}${detalhe ? "  — " + detalhe : ""}`);
  if (!cond) falhas++;
};

const base = ler("base.json");
const ordem = ler("ordem.json");
const mapa = ler("mapa.json");
const modelo = new Modelo(base);

const idx = new Map();
for (let i = 0; i < base.ufs.length; i++) {
  idx.set(base.ufs[i] + "/" + base.cds[i], i);
}
const eleitoradoTotal = base.ele.reduce((a, b) => a + b, 0);
const realPL = 100 * base.pl.reduce((a, b) => a + b, 0) /
  (base.pl.reduce((a, b) => a + b, 0) + base.pt.reduce((a, b) => a + b, 0));

function estadoEm(pctAlvo) {
  const limite = (pctAlvo / 100) * eleitoradoTotal;
  const fracoes = new Map();
  const observado = {};
  let acc = 0;
  for (const chave of ordem) {
    if (acc >= limite) break;
    const i = idx.get(chave);
    if (i === undefined) continue;
    fracoes.set(chave, 1);
    const uf = base.ufs[i];
    if (!observado[uf]) observado[uf] = { pl: 0, pt: 0 };
    observado[uf].pl += base.pl[i];
    observado[uf].pt += base.pt[i];
    acc += base.ele[i];
  }
  return { fracoes, observado };
}

console.log(`Testando o site — ${REPS} repetições por bloco.\n`);

// ---------------------------------------------------------------- 1
console.log("1. MODELO EM VÁRIOS PONTOS DA APURAÇÃO");
console.log("   (base e alvo são o mesmo 1º turno, então o erro certo é ~0)");
for (const pct of [0.5, 1, 5, 10, 20, 50]) {
  const { fracoes, observado } = estadoEm(pct);
  const r = modelo.projetar(fracoes, observado, 120);
  let bPl = 0, bTot = 0;
  for (const u of Object.values(observado)) { bPl += u.pl; bTot += u.pl + u.pt; }
  const bruto = 100 * bPl / bTot;
  const erro = Math.abs(r.projecaoPl - realPL);
  ok(erro < 0.6,
     `${String(pct).padStart(4)}% apurado: projeção ${r.projecaoPl.toFixed(2)}%`,
     `erro ${erro.toFixed(2)} pp (bruto erraria ${Math.abs(bruto - realPL).toFixed(1)} pp)`);
}

// determinismo: a mesma entrada tem que dar a mesma saída sempre
console.log("\n2. ESTABILIDADE (a mesma entrada dá sempre o mesmo número?)");
for (let k = 0; k < REPS; k++) {
  const { fracoes, observado } = estadoEm(5);
  const a = modelo.projetar(fracoes, observado, 120);
  const b = modelo.projetar(fracoes, observado, 120);
  ok(a.projecaoPl === b.projecaoPl && a.faixaPl[0] === b.faixaPl[0],
     `repetição ${k + 1}: ${a.projecaoPl.toFixed(4)}% e faixa idênticas`);
}

// ---------------------------------------------------------------- 3
console.log("\n3. MAPA");
const UFS_ESPERADAS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG",
  "MS","MT","PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"];
ok(Object.keys(mapa.ufs).length === 27, `27 estados no mapa`,
   `vieram ${Object.keys(mapa.ufs).length}`);
const faltando = UFS_ESPERADAS.filter((u) => !mapa.ufs[u]);
ok(faltando.length === 0, "nenhum estado faltando",
   faltando.length ? faltando.join(",") : "");
ok(UFS_ESPERADAS.every((u) => mapa.rotulos[u]), "todos têm ponto de rótulo");
const pathsOk = Object.entries(mapa.ufs).every(([, d]) =>
  d.startsWith("M") && d.endsWith("Z") && d.length > 50);
ok(pathsOk, "todos os contornos são caminhos SVG válidos");
// rótulo dentro da área do mapa
const [, , vw, vh] = mapa.viewBox.split(" ").map(Number);
const rotulosDentro = Object.values(mapa.rotulos).every(
  ([x, y]) => x >= 0 && x <= vw && y >= 0 && y <= vh);
ok(rotulosDentro, "todos os rótulos caem dentro do mapa");
// cada estado recebe cor em qualquer ponto da apuração
for (const pct of [1, 5, 20]) {
  const { fracoes, observado } = estadoEm(pct);
  const r = modelo.projetar(fracoes, observado, 0);
  const comProj = r.estados.filter((e) => mapa.ufs[e.uf]).length;
  ok(comProj === 27, `com ${pct}% apurado, os 27 estados têm projeção`,
     `vieram ${comProj}`);
}

// ---------------------------------------------------------------- 4
console.log("\n4. ORDEM DE CHEGADA");
ok(ordem.length > 5000, `${ordem.length} municípios na ordem`);
const semBase = ordem.filter((c) => !idx.has(c)).length;
ok(semBase / ordem.length < 0.02, "quase todos casam com a base",
   `${semBase} sem correspondência`);
const { observado: o5 } = estadoEm(5);
const ufs5 = Object.keys(o5).length;
ok(ufs5 >= 15, `com 5% apurado já há ${ufs5} estados com voto`);

// ---------------------------------------------------------------- 5
console.log(`\n5. PESQUISAS (${REPS} leituras da Wikipédia)`);
let listaPesq = null;
for (let k = 0; k < REPS; k++) {
  try {
    const lista = await pq.buscarSegundoTurno();
    listaPesq = lista;
    const ag = pq.agregar(lista);
    ok(lista.length > 5 && ag && ag.pl > 30 && ag.pl < 70,
       `leitura ${k + 1}: ${lista.length} pesquisas, média ${ag ? ag.pl.toFixed(2) : "—"}%`,
       ag ? `faixa ${ag.faixa[0].toFixed(2)}–${ag.faixa[1].toFixed(2)}` : "");
  } catch (e) {
    ok(false, `leitura ${k + 1} falhou`, e.message);
  }
}
if (listaPesq) {
  const datasOk = listaPesq.every((p) => p.fim instanceof Date && !isNaN(p.fim));
  ok(datasOk, "todas as pesquisas têm data válida");
  const pctOk = listaPesq.every((p) => p.pl >= 0 && p.pl <= 100 && p.pt >= 0 && p.pt <= 100);
  ok(pctOk, "todos os percentuais são plausíveis");
}

// ---------------------------------------------------------------- 6
console.log(`\n6. LEITURA AO VIVO DO TSE (${REPS} leituras do 2º turno)`);
for (let k = 0; k < REPS; k++) {
  const t0 = Date.now();
  try {
    const { observado, fracoes, totais, falhas: f } = await tse.lerTudo(tse.ELEICAO_2T);
    const ufs = Object.keys(observado).length;
    const ms = Date.now() - t0;
    ok(ufs >= 27 && f.length === 0,
       `leitura ${k + 1}: ${ufs} UFs em ${(ms / 1000).toFixed(1)}s`,
       `${totais.secoes.toLocaleString("pt-BR")} seções, ${f.length} falhas`);
    ok(ms < 25000, `   dentro do ciclo de 25s`, `${(ms / 1000).toFixed(1)}s`);
  } catch (e) {
    ok(false, `leitura ${k + 1} falhou`, e.message);
  }
}

console.log(falhas === 0
  ? "\nTUDO PASSOU."
  : `\n${falhas} FALHA(S) — veja acima.`);
process.exit(falhas === 0 ? 0 : 1);
