/*
 * Segurança e privacidade, testadas no navegador contra o site publicado.
 *
 * A superfície de ataque desta página é pequena mas não é zero, e tem um
 * ponto fraco óbvio: ela lê a Wikipédia, que qualquer pessoa do mundo pode
 * editar. Um nome de instituto é texto de terceiro entrando na página.
 *
 * Então aqui a Wikipédia é substituída por uma resposta hostil, montada com
 * os vetores que de fato funcionam contra uma página assim, e verifica-se
 * que nada executa. Além disso: para onde os dados vão, o que fica guardado
 * no aparelho, e se a política de conteúdo está realmente valendo.
 *
 * Uso:  node programa/testar_seguranca.mjs [url]
 */

import puppeteer from "puppeteer-core";

const CHROME = "/root/.cache/puppeteer/chrome/linux-131.0.6778.204/"
  + "chrome-linux64/chrome";
const SITE = process.argv[2] || "http://localhost:8899/";

/* Hospedeiros que a página tem motivo para procurar. Qualquer outro é
 * vazamento, seja de dado, seja de atenção. */
// O host do próprio site sai da URL testada, senão rodar contra um servidor
// local acusa "localhost" como vazamento — falso positivo que esconde os
// verdadeiros no meio.
// O contador de visitas entra aqui porque é um destino que a página tem
// motivo para procurar — mas ele só pode aparecer como UM PIXEL. Se algum dia
// virar um script carregado de fora, é gc.zgo.at que apareceria nesta lista,
// e aí a reprovação é desejada: a decisão de não rodar código de terceiro na
// página não deve poder ser revertida sem alguém perceber.
const ESPERADOS = [new URL(SITE).hostname,
                   "resultados.tse.jus.br", "pt.wikipedia.org",
                   "oxeapuracao.goatcounter.com"];

/* Nomes de instituto com carga: cada um é uma forma diferente de fazer
 * código rodar numa página que monta HTML com texto de fora. */
const VENENOS = [
  '<img src=x onerror="window.__INVADIU=1">',
  '<script>window.__INVADIU=1<\/script>',
  '<svg onload="window.__INVADIU=1">',
  '"><iframe src="javascript:window.__INVADIU=1"></iframe>',
  "<a href=\"javascript:window.__INVADIU=1\">clique</a>",
  '<style>@import "https://exemplo.invalido/x.css";</style>',
  '<img src="https://exemplo.invalido/rastreador.gif">',
];

/* Resposta da Wikipédia com os venenos no lugar dos nomes de instituto. */
function wikiHostil(req) {
  const u = req.url();
  const corpo = u.includes("prop=sections")
    ? { parse: { sections: [
        { index: "1", line: "Lula e Flávio Bolsonaro" },
        { index: "2", line: "Primeiro turno" },
      ] } }
    : { parse: { text: { "*": `
      <table><tr><th>a</th></tr></table>
      <table>
        <tr><th>Instituto</th><th>Data</th><th>Amostra</th><th>Margem</th>
            <th>Lula</th><th>Flávio</th><th>Ind.</th><th>Vant.</th></tr>
        ${VENENOS.map((v, i) => `
        <tr><td>${v}</td><td>1${i} Out – 1${i} Out</td><td>2000</td>
            <td>2,0</td><td>48</td><td>50</td><td>2</td><td>2</td></tr>`).join("")}
      </table>` } } };
  return req.respond({
    status: 200,
    headers: { "Access-Control-Allow-Origin": "*" },
    contentType: "application/json",
    body: JSON.stringify(corpo),
  });
}

const nav = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const falhas = [];
const p = await nav.newPage();
const hospedeiros = new Set();
const bloqueadosPelaCSP = [];

p.on("request", (r) => {
  try { hospedeiros.add(new URL(r.url()).hostname); } catch {}
});
p.on("console", (m) => {
  const t = m.text();
  if (/Content Security Policy/i.test(t)) bloqueadosPelaCSP.push(t.slice(0, 80));
});

await p.setRequestInterception(true);
p.on("request", (req) => {
  if (req.url().includes("wikipedia.org")) return wikiHostil(req);
  return req.continue();
});

await p.goto(SITE, { waitUntil: "networkidle2", timeout: 90000 });
await new Promise((r) => setTimeout(r, 4000));
// Abre a aba de pesquisas: é onde o texto de terceiro vira HTML.
await p.evaluate(() => {
  const b = [...document.querySelectorAll(".aba")].find((x) => x.dataset.aba === "pesquisas");
  if (b) b.click();
});
await new Promise((r) => setTimeout(r, 8000));

const d = await p.evaluate(() => ({
  invadiu: !!window.__INVADIU,
  // Elementos que NÃO deveriam existir: se o texto virou marcação, viraram nós.
  scripts: document.querySelectorAll("script:not([type='module'])").length,
  iframes: document.querySelectorAll("iframe").length,
  objetos: document.querySelectorAll("object,embed").length,
  onerror: document.querySelectorAll("[onerror],[onload]:not(body)").length,
  linksJs: [...document.querySelectorAll("a[href^='javascript:']")].length,
  // O veneno aparece como TEXTO? Isso é o correto: escapado, visível, inerte.
  comoTexto: /img src=x onerror/.test(document.body.innerText),
  // O que ficou guardado no aparelho.
  local: Object.keys(localStorage),
  session: Object.keys(sessionStorage),
  cookies: document.cookie,
  csp: (document.querySelector('meta[http-equiv="Content-Security-Policy"]') || {}).content || "",
}));

console.log(`\nSegurança — ${SITE}\n${"=".repeat(68)}`);

// 1. Execução de código de terceiro
console.log("\n1. Texto vindo da Wikipédia (qualquer um edita)");
if (d.invadiu) falhas.push("CÓDIGO DE TERCEIRO EXECUTOU (XSS)");
console.log(`   código executou ............ ${d.invadiu ? "SIM ✗" : "não ✓"}`);
console.log(`   virou <script> ............. ${d.scripts ? d.scripts + " ✗" : "não ✓"}`);
console.log(`   virou <iframe> ............. ${d.iframes ? d.iframes + " ✗" : "não ✓"}`);
console.log(`   virou <object>/<embed> ..... ${d.objetos ? d.objetos + " ✗" : "não ✓"}`);
console.log(`   ganhou onerror/onload ...... ${d.onerror ? d.onerror + " ✗" : "não ✓"}`);
console.log(`   link javascript: ........... ${d.linksJs ? d.linksJs + " ✗" : "não ✓"}`);
console.log(`   apareceu escapado, como texto  ${d.comoTexto ? "sim ✓" : "não (verifique)"}`);
for (const [rot, v] of [["script", d.scripts], ["iframe", d.iframes],
                        ["object/embed", d.objetos], ["onerror/onload", d.onerror],
                        ["link javascript:", d.linksJs]]) {
  if (v) falhas.push(`texto de terceiro virou ${rot} na página`);
}

// 2. Para onde os dados vão
console.log("\n2. Destinos procurados pela página");
const intrusos = [...hospedeiros].filter((h) => !ESPERADOS.includes(h));
for (const h of hospedeiros) {
  console.log(`   ${ESPERADOS.includes(h) ? "✓" : "✗"} ${h}`);
}
if (intrusos.length) falhas.push("falou com hospedeiro inesperado: " + intrusos.join(", "));
console.log(`   (o veneno pedia uma imagem em exemplo.invalido — se não está`);
console.log(`    na lista acima, a política de conteúdo barrou antes de sair)`);

// 3. O que fica no aparelho
console.log("\n3. Guardado no aparelho de quem visita");
console.log(`   localStorage ... ${d.local.join(", ") || "(nada)"}`);
console.log(`   sessionStorage . ${d.session.join(", ") || "(nada)"}`);
console.log(`   cookies ........ ${d.cookies || "(nenhum)"}`);
if (d.cookies) falhas.push("a página criou cookie");

// 4. Política de conteúdo
console.log("\n4. Política de conteúdo (CSP)");
const precisa = ["default-src 'none'", "object-src", "base-uri", "form-action"];
for (const t of precisa) {
  const tem = d.csp.includes(t.split(" ")[0]);
  console.log(`   ${tem ? "✓" : "✗"} ${t.split(" ")[0]}`);
  if (!tem) falhas.push("CSP sem " + t.split(" ")[0]);
}
if (bloqueadosPelaCSP.length) {
  console.log(`   a CSP barrou ${bloqueadosPelaCSP.length} tentativa(s) durante o teste:`);
  bloqueadosPelaCSP.slice(0, 3).forEach((t) => console.log(`     · ${t}`));
}

await nav.close();
console.log(`\n${"=".repeat(68)}`);
if (falhas.length) {
  falhas.forEach((f) => console.log("✗ " + f));
  process.exit(1);
}
console.log("tudo certo: nada executou, nada vazou, nada ficou guardado indevidamente");
