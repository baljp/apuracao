/*
 * Votos de um estado chegam, o andamento dele não (e vice-versa).
 *
 * Este é o cenário que uma auditoria externa apontou e que nenhum teste
 * daqui cobria — porque todos os outros tratam a falha de um ESTADO inteiro,
 * e aqui a falha é de METADE de um estado: um dos dois arquivos chega e o
 * outro não.
 *
 * Por que importa: os votos de uma UF e o andamento dela vêm de arquivos
 * diferentes do TSE. Se os votos de São Paulo chegam e o andamento falha, o
 * modelo soma 22 milhões de votos observados e, como não sabe que nada foi
 * apurado ali, projeta São Paulo inteiro por cima. Os mesmos votos entram
 * duas vezes, e a tela não mostra nada de errado — um número plausível,
 * calculado em dobro.
 *
 * O teste força os dois sentidos do descasamento e exige que a UF afetada
 * saia inteira da conta, aparecendo como estado sem resposta.
 *
 * Uso:  node programa/testar_desencontro.mjs [url]
 */

import puppeteer from "puppeteer-core";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const CHROME = "/root/.cache/puppeteer/chrome/linux-131.0.6778.204/"
  + "chrome-linux64/chrome";
const SITE = process.argv[2] || "http://localhost:8899/";
const NOITE = Date.UTC(2026, 9, 25, 21, 0);
const CORS = { "Access-Control-Allow-Origin": "*" };

const CACHE = new Map();
const dir = join(dirname(fileURLToPath(import.meta.url)), "mock_1t");
for (const nome of readdirSync(dir)) {
  CACHE.set(nome, readFileSync(join(dir, nome), "utf-8"));
}
if (CACHE.size < 50) {
  console.error("faltam arquivos em programa/mock_1t — rode baixar_mock.sh");
  process.exit(2);
}

/* São Paulo é o caso mais severo: sozinho é 22% do eleitorado. */
const CENARIOS = [
  {
    nome: "CONTROLE — tudo chega",
    falta: null,
    espero: "projeção normal, nenhum estado fora",
  },
  {
    nome: "votos de SP chegam, andamento de SP falha",
    falta: (nome) => nome.startsWith("sp-") && nome.includes("-ab.json"),
    espero: "SP sai inteiro da conta e aparece como sem resposta",
  },
  {
    nome: "andamento de SP chega, votos de SP falham",
    falta: (nome) => nome.startsWith("sp-") && nome.includes("-u.json"),
    espero: "SP sai inteiro da conta e aparece como sem resposta",
  },
  {
    nome: "metade dos estados com andamento faltando",
    falta: (nome) => nome.includes("-ab.json") && nome[0] < "n",
    espero: "esses estados saem da conta; os demais projetam normalmente",
  },
];

const nav = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

console.log(`\nDescasamento entre votos e andamento — ${SITE}`);
console.log("=".repeat(76));

let referencia = null;
let reprovados = 0;

for (const c of CENARIOS) {
  const p = await nav.newPage();
  const erros = [];
  p.on("pageerror", (e) => erros.push(e.message.slice(0, 70)));

  await p.evaluateOnNewDocument((fixo) => {
    const D = Date, delta = fixo - D.now();
    window.Date = class extends D {
      constructor(...a) { if (!a.length) super(D.now() + delta); else super(...a); }
      static now() { return D.now() + delta; }
    };
  }, NOITE);

  await p.setRequestInterception(true);
  p.on("request", (req) => {
    const u = req.url();
    if (!u.includes("resultados.tse.jus.br")) return req.continue();
    const nome = u.split("/").pop();
    if (c.falta && c.falta(nome)) {
      return req.respond({ status: 503, headers: CORS, body: "" });
    }
    const txt = CACHE.get(nome);
    if (txt === undefined) return req.respond({ status: 404, headers: CORS, body: "" });
    return req.respond({ status: 200, headers: CORS,
                         contentType: "application/json", body: txt });
  });

  await p.goto(SITE, { waitUntil: "domcontentloaded", timeout: 60000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 9000));

  const d = await p.evaluate(() => {
    const n = (id) => {
      const e = document.getElementById(id);
      const v = parseFloat((e ? e.textContent : "").replace("%", "").replace(",", "."));
      return isFinite(v) ? v : null;
    };
    return {
      projecao: n("pctPL"),
      apurado: n("apurado"),
      status: (document.getElementById("status") || {}).textContent || "",
      placar: getComputedStyle(document.getElementById("placar")).display !== "none",
    };
  }).catch(() => ({ projecao: null, apurado: null, status: "(sem resposta)", placar: false }));

  const semResposta = (d.status.match(/(\d+) estado\(s\) sem resposta/) || [])[1];
  const problemas = [];

  if (c.falta === null) {
    referencia = d.projecao;
    if (!d.placar) problemas.push("controle não produziu placar");
  } else {
    // O teste decisivo: a projeção não pode se deslocar porque metade do
    // dado de um estado faltou. Se deslocar, houve contagem em dobro.
    if (referencia !== null && d.projecao !== null) {
      const desvio = Math.abs(d.projecao - referencia);
      if (desvio > 0.6) {
        problemas.push(`projeção deslocou ${desvio.toFixed(2)} pp — sinal de`
          + " dado contado em dobro");
      }
    }
    if (!semResposta) {
      problemas.push("não avisou que há estado sem resposta");
    }
  }
  if (erros.length) problemas.push("erro de JS: " + erros[0]);
  if (problemas.length) reprovados++;

  console.log(`\n${problemas.length ? "✗" : "✓"} ${c.nome}`);
  console.log(`    espero    : ${c.espero}`);
  console.log(`    projeção  : ${d.projecao === null ? "—" : d.projecao.toFixed(2) + "%"}`
    + `   apurado: ${d.apurado === null ? "—" : d.apurado.toFixed(1) + "%"}`
    + `   sem resposta: ${semResposta || "0"}`);
  problemas.forEach((x) => console.log(`    ⚠ ${x}`));
  await p.close();
}

await nav.close();
console.log(`\n${"=".repeat(76)}`);
console.log(reprovados ? `${reprovados} cenário(s) reprovado(s)`
                       : "dado pela metade nunca entra no cálculo");
process.exit(reprovados ? 1 : 0);
