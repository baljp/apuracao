/*
 * Confere que o modelo em JavaScript — o que roda no site — dá o mesmo
 * resultado que o modelo em Python, que é onde a acurácia foi medida.
 *
 * O conferir.mjs já fazia essa comparação, mas só com 100% apurado: ponto em
 * que não sobra nada para projetar e qualquer modelo acerta. Um teste que só
 * pergunta o que não precisa de modelo não testa modelo nenhum — e foi por
 * isso que uma divergência real passou despercebida. O Python corrigia o
 * volume do que falta pelo rendimento de voto válido do 2º turno e o
 * JavaScript não; os dois concordavam em 100% e divergiam no meio da noite,
 * que é quando a página é usada.
 *
 * Aqui a comparação é feita em onze pontos da apuração, com os mesmos dados
 * de entrada dos dois lados, incluindo margem, probabilidade e cada estado.
 *
 * Uso:
 *   python3 programa/paridade.py     (gera os cenários)
 *   node paridade.mjs
 */

import { readFileSync } from "node:fs";
import { Modelo } from "./modelo.js";

// Diferenças toleradas. Não são "margem de erro": são o limite do que
// aritmética de ponto flutuante explica. Qualquer coisa acima disso é
// divergência de lógica entre os dois modelos.
const TOL_PROJECAO = 1e-6;   // pontos percentuais
const TOL_ESTADO = 1e-5;

// A margem e a probabilidade saem de um bootstrap, e os dois lados sorteiam
// com geradores diferentes — então elas NÃO podem bater dígito a dígito. O
// que se exige aqui é que a diferença seja compatível com ruído amostral de
// 240 sorteios, e não com divergência de lógica.
//
// Medido: a diferença cai com a raiz do número de amostras (0,109 pp com
// 240, 0,055 com 1000, 0,032 com 4000), que é exatamente a assinatura de
// ruído. Divergência de lógica não encolheria assim.
const TOL_MARGEM = 0.18;
const TOL_PROB = 0.05;

const base = JSON.parse(readFileSync(new URL("./base.json", import.meta.url)));
const cenarios = JSON.parse(readFileSync(
  new URL("./programa/cenarios_paridade.json", import.meta.url)));

const modelo = new Modelo(base);
let falhas = 0;

console.log("\nParidade Python × JavaScript, em apuração parcial");
console.log("=".repeat(72));
console.log("apurado    projeção py    projeção js    diferença   margem  estados");
console.log("-".repeat(72));

for (const c of cenarios) {
  const andamento = new Map(Object.entries(c.andamento));
  const r = modelo.projetar(andamento, c.observado, 240);
  const py = c.python;

  const dProj = Math.abs(r.projecaoPl - py.projecao_pl);
  const dLo = Math.abs(r.faixaPl[0] - py.faixa_pl[0]);
  const dHi = Math.abs(r.faixaPl[1] - py.faixa_pl[1]);
  const dProb = Math.abs(r.probPl - py.prob_pl);

  let piorEstado = 0, ufPior = "";
  for (const e of r.estados) {
    const alvo = py.estados[e.uf];
    if (alvo === undefined) continue;
    const d = Math.abs(e.projPl - alvo);
    if (d > piorEstado) { piorEstado = d; ufPior = e.uf; }
  }

  const problemas = [];
  if (dProj > TOL_PROJECAO) problemas.push(`projeção difere em ${dProj.toFixed(6)} pp`);
  if (dLo > TOL_MARGEM || dHi > TOL_MARGEM) {
    problemas.push(`margem difere em ${Math.max(dLo, dHi).toFixed(4)} pp —`
      + ` acima do ruído esperado de 240 sorteios`);
  }
  if (dProb > TOL_PROB) problemas.push(`probabilidade difere em ${dProb.toFixed(4)}`);
  if (piorEstado > TOL_ESTADO) {
    problemas.push(`${ufPior} difere em ${piorEstado.toFixed(6)} pp`);
  }
  if (problemas.length) falhas++;

  console.log(
    `${String(c.marco).padStart(6)}%  ${py.projecao_pl.toFixed(6).padStart(13)}`
    + `  ${r.projecaoPl.toFixed(6).padStart(13)}  ${dProj.toExponential(1).padStart(10)}`
    + `  ${Math.max(dLo, dHi).toExponential(1).padStart(7)}`
    + `  ${piorEstado.toExponential(1).padStart(7)}`
    + (problemas.length ? "  ✗ " + problemas.join("; ") : "  ok"));
}

console.log("=".repeat(72));
if (falhas) {
  console.log(`${falhas} cenário(s) divergem — o site NÃO roda o modelo que foi medido`);
  process.exit(1);
}
console.log("os dois modelos concordam em toda a noite, até a margem e cada estado");
