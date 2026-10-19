/*
 * O que acontece quando o mundo lá fora quebra?
 *
 * Todos os outros testes deste projeto assumem que o TSE responde e responde
 * certo. Na noite da eleição essa é justamente a hipótese que não se pode
 * assumir: servidor sobrecarregado, resposta pela metade, arquivo corrompido
 * por um proxy no meio do caminho, operadora lenta, Wikipédia fora.
 *
 * Aqui cada cenário é forçado interceptando as requisições no navegador. O
 * critério de aprovação não é "funcionou": é que a página NUNCA mostre um
 * número errado. Diante de dado ruim, ela tem de mostrar dado nenhum.
 *
 * Uso:  node programa/testar_resiliencia.mjs [url]
 */

import puppeteer from "puppeteer-core";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const CHROME = "/root/.cache/puppeteer/chrome/linux-131.0.6778.204/"
  + "chrome-linux64/chrome";
/* Endereço padrão: a cópia local servida por `python3 -m http.server 8899`,
 * que é a versão que está sendo mexida agora. Apontar para um site publicado
 * já fez este teste mentir: ficou meses com um endereço que havia saído do ar,
 * e todo cenário respondia 404 — nenhum chegava a exercitar o modelo, e os que
 * só verificavam ausência de número passavam. Por isso há um CONTROLE no fim,
 * que reprova se dado bom não produzir placar. */
const SITE = process.argv[2] || "http://localhost:8899/";

// Durante a apuração, para que a página realmente fale com o TSE.
const NOITE = Date.UTC(2026, 9, 25, 21, 0);   // 18h de Brasília

const eTSE = (u) => u.includes("resultados.tse.jus.br");
const eWiki = (u) => u.includes("wikipedia.org");

/* A fonte dos dados bons: a eleição do 1º turno, que já aconteceu e está
 * 100% apurada no TSE. Trocando o código 6258 (2º turno, ainda vazio) por
 * 6257 na hora da requisição, a página roda com dados REAIS e completos —
 * e aí sim há um placar na tela para os cenários de falha estragarem.
 *
 * Sem isso o teste passa por engano: se o dado falso não é sequer aceito
 * pelo modelo, "não apareceu número errado" não prova nada, porque não
 * apareceu número nenhum em caso nenhum. Foi exatamente o que aconteceu na
 * primeira versão deste arquivo. */
const paraPrimeiroTurno = (u) => u.replace(/e006258/g, "e006257")
                                  .replace(/\/6258\//g, "/6257/");

/* Os arquivos verdadeiros, baixados UMA vez antes dos testes.
 *
 * A primeira tentativa buscava cada arquivo dentro do próprio interceptador,
 * com await. Não funciona: a resposta chega depois de a página ter desistido,
 * e o cenário termina sem ter exercitado nada — passando por engano. Com tudo
 * em memória, a resposta é instantânea e o teste é real.
 */
const CACHE = new Map();

function precarregar() {
  // Os arquivos vêm do disco e não da rede: o fetch do Node não usa o proxy
  // deste ambiente, então baixar aqui devolvia cache vazio e TODOS os
  // cenários "passavam" sem ter exercitado nada. Populados por
  //     programa/baixar_mock.sh
  const dir = join(dirname(fileURLToPath(import.meta.url)), "mock_1t");
  for (const nome of readdirSync(dir)) {
    CACHE.set(nome, readFileSync(join(dir, nome), "utf-8"));
  }
  if (CACHE.size < 50) {
    console.error("faltam arquivos em programa/mock_1t — rode baixar_mock.sh");
    process.exit(2);
  }
  console.log(`  ${CACHE.size} arquivos reais do 1º turno em memória`);
}

/* Serve o arquivo verdadeiro, já passado pela função de estrago. */
// O TSE serve com Access-Control-Allow-Origin: *. Uma resposta forjada sem
// esse cabeçalho é descartada pelo navegador antes de chegar ao código da
// página — e o cenário termina sem ter exercitado nada, passando por engano.
// Foi o que escondeu três falsos "ok" nas primeiras versões deste arquivo.
const CORS = { "Access-Control-Allow-Origin": "*" };

function servirAlterado(req, alterar) {
  const nome = req.url().split("/").pop();
  const txt = CACHE.get(nome);
  if (txt === undefined) return req.respond({ status: 404, headers: CORS, body: "" });
  return req.respond({ status: 200, headers: CORS,
                       contentType: "application/json", body: alterar(txt) });
}

/* Serve o arquivo verdadeiro, intacto. */
const servirReal = (req) => servirAlterado(req, (t) => t);

const CENARIOS = [
  {
    nome: "CONTROLE — dados reais e completos",
    exigeplacar: true,
    rota: (req) => eTSE(req.url())
      ? servirReal(req) : req.continue(),
    espero: "placar na tela com percentuais válidos (se falhar, os demais não valem)",
  },
  {
    nome: "TSE inteiro fora do ar (503)",
    rota: (req) => eTSE(req.url()) ? req.respond({ status: 503, headers: CORS, body: "" }) : req.continue(),
    espero: "sem número na tela",
  },
  {
    nome: "TSE devolve lixo no lugar de JSON",
    rota: (req) => eTSE(req.url())
      ? req.respond({ status: 200, headers: CORS, contentType: "application/json",
                      body: "<html>502 Bad Gateway</html>" })
      : req.continue(),
    espero: "sem número na tela",
  },
  {
    nome: "TSE devolve JSON truncado pela metade",
    rota: (req) => eTSE(req.url())
      ? servirAlterado(req, (t) => t.slice(0, Math.floor(t.length / 2)))
      : req.continue(),
    espero: "sem número na tela",
  },
  {
    nome: "metade dos estados fora do ar",
    exigeplacar: true,
    rota: (req) => {
      const u = req.url();
      if (!eTSE(u)) return req.continue();
      const uf = (u.match(/\/([a-z]{2})\/[a-z]{2}-/) || [])[1] || "";
      if (uf < "n") return req.respond({ status: 500, headers: CORS, body: "" });
      return servirReal(req);
    },
    espero: "projeta com o que tem e avisa quantos estados faltam",
  },
  {
    nome: "votos negativos",
    rota: (req) => eTSE(req.url())
      ? servirAlterado(req, (t) => t.replace(/"vap"\s*:\s*"(\d+)"/g, '"vap" : "-$1"'))
      : req.continue(),
    espero: "nenhum NaN, nenhum percentual fora de 0–100",
  },
  {
    nome: "votos absurdamente grandes",
    rota: (req) => eTSE(req.url())
      ? servirAlterado(req, (t) => t.replace(/"vap"\s*:\s*"(\d+)"/g, '"vap" : "9999999999999"'))
      : req.continue(),
    espero: "nenhum NaN, nenhum percentual fora de 0–100",
  },
  {
    nome: "andamento diz 200% apurado",
    exigeplacar: true,
    rota: (req) => {
      const u = req.url();
      if (!eTSE(u)) return req.continue();
      if (!u.includes("-ab.json")) return servirReal(req);
      return servirAlterado(req, (t) => t.replace(/"est"\s*:\s*"(\d+)"/g,
        (_, n) => '"est" : "' + (parseInt(n, 10) * 2) + '"'));
    },
    espero: "apurado não passa de 100%",
  },
  {
    nome: "TSE lento demais (20s por arquivo)",
    lento: true, semVeredito: true,
    rota: async (req) => {
      if (!eTSE(req.url())) return req.continue();
      await new Promise((r) => setTimeout(r, 20000));
      req.respond({ status: 200, headers: CORS, contentType: "application/json", body: "{}" });
    },
    espero: "página não trava nem congela a interface",
  },
  {
    nome: "Wikipédia fora do ar",
    exigeplacar: true,
    rota: (req) => {
      const u = req.url();
      if (eWiki(u)) return req.respond({ status: 503, headers: CORS, body: "" });
      if (eTSE(u)) return servirReal(req);
      return req.continue();
    },
    espero: "apuração segue normal; pesquisas apenas ausentes",
  },
];

function veredito(d) {
  const falhas = [];
  if (d.erroJS.length) falhas.push("erro de JS: " + d.erroJS[0]);
  if (/NaN|undefined|Infinity/.test(d.textoVisivel)) {
    falhas.push("texto com NaN/undefined: "
      + (d.textoVisivel.match(/[^\n]*(NaN|undefined|Infinity)[^\n]*/) || [])[0]);
  }
  for (const [rotulo, v] of Object.entries(d.percentuais)) {
    if (v === null) continue;
    if (!(v >= 0 && v <= 100)) falhas.push(`${rotulo} fora de 0–100: ${v}`);
  }
  if (d.congelou) falhas.push("interface congelada (não respondeu a clique)");
  if (d.exigeplacar && !d.placarVisivel) {
    falhas.push("esperava placar na tela e não apareceu — o cenário não chegou "
      + "a exercitar o modelo, então não prova nada");
  }
  if (!d.exigeplacar && d.placarVisivel) {
    falhas.push("MOSTROU NÚMERO a partir de dado inválido");
  }
  return falhas;
}

precarregar();

const nav = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

let reprovados = 0;
console.log(`\nResiliência — ${SITE}\n${"=".repeat(68)}`);

for (const c of CENARIOS) {
  const p = await nav.newPage();
  const erroJS = [];
  p.on("pageerror", (e) => erroJS.push(e.message.slice(0, 90)));

  await p.evaluateOnNewDocument((fixo) => {
    const D = Date, delta = fixo - D.now();
    window.Date = class extends D {
      constructor(...a) { if (!a.length) super(D.now() + delta); else super(...a); }
      static now() { return D.now() + delta; }
    };
  }, NOITE);

  await p.setRequestInterception(true);
  p.on("request", (req) => { Promise.resolve(c.rota(req)).catch(() => { try { req.continue(); } catch {} }); });

  try {
    await p.goto(SITE, { waitUntil: "domcontentloaded", timeout: 60000 });
  } catch { /* um cenário pode impedir o load completo; segue */ }
  await new Promise((r) => setTimeout(r, c.lento ? 14000 : 9000));

  const d = await p.evaluate(() => {
    const num = (id) => {
      const e = document.getElementById(id);
      if (!e) return null;
      const t = e.textContent.replace("%", "").replace(",", ".").trim();
      const v = parseFloat(t);
      return isFinite(v) ? v : null;
    };
    return {
      textoVisivel: document.body.innerText,
      percentuais: { pctPL: num("pctPL"), pctPT: num("pctPT"), apurado: num("apurado") },
      placarVisivel: getComputedStyle(document.getElementById("placar")).display !== "none",
      status: (document.getElementById("status") || {}).textContent || "",
      faixa: (document.getElementById("statusTitulo") || {}).textContent || "",
    };
  }).catch(() => ({ textoVisivel: "", percentuais: {}, status: "(página não respondeu)",
                    faixa: "", placarVisivel: false }));

  // A interface ainda responde? Clicar numa aba é o teste mais simples.
  let congelou = false;
  try {
    await Promise.race([
      p.evaluate(() => {
        const b = [...document.querySelectorAll(".aba")].find((x) => x.dataset.aba === "pesquisas");
        if (b) b.click();
        return true;
      }),
      new Promise((_, rej) => setTimeout(() => rej(new Error("tempo")), 5000)),
    ]);
  } catch { congelou = true; }

  const falhas = veredito({ ...d, erroJS, congelou, exigeplacar: !!c.exigeplacar });
  if (falhas.length) reprovados++;
  console.log(`\n${falhas.length ? "✗" : "✓"} ${c.nome}`);
  console.log(`    espero : ${c.espero}`);
  console.log(`    faixa  : ${d.faixa.trim().slice(0, 62)}`);
  console.log(`    status : ${d.status.trim().slice(0, 62)}`);
  console.log(`    placar : ${d.placarVisivel ? "mostrando número" : "escondido"}`);
  falhas.forEach((f) => console.log(`    ⚠ ${f}`));
  await p.close();
}

await nav.close();
console.log(`\n${"=".repeat(68)}`);
console.log(reprovados ? `${reprovados} cenário(s) reprovado(s)`
                       : "todos os cenários passaram");
process.exit(reprovados ? 1 : 0);
