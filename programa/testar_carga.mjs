/*
 * Carga e resistência: muita gente ao mesmo tempo, e uma aba aberta a noite
 * inteira.
 *
 * São dois medos diferentes e um não cobre o outro.
 *
 * O primeiro é o óbvio: milhares de pessoas abrindo a página ao mesmo tempo.
 * Como o site é estático num CDN, o que se mede aqui não é "o servidor
 * aguenta" — aguenta — e sim quanto cada visita custa, para multiplicar pelo
 * número de pessoas e saber o que isso representa em banda e em requisições
 * ao TSE.
 *
 * O segundo é o que ninguém testa e é o que de fato quebra numa noite de
 * apuração: a aba que fica aberta das 17h às 23h, atualizando a cada 25
 * segundos. Se cada atualização deixar um pedaço de memória para trás, em
 * seis horas o celular fica lento e depois mata a aba — justamente na hora
 * em que o resultado está saindo. Aqui o tempo é acelerado para medir isso
 * em minutos.
 *
 * Uso:
 *   node programa/testar_carga.mjs                 tudo
 *   node programa/testar_carga.mjs simultaneas 30  só a carga, com 30 abas
 *   node programa/testar_carga.mjs longa           só a sessão longa
 */

import puppeteer from "puppeteer-core";

const CHROME = "/root/.cache/puppeteer/chrome/linux-131.0.6778.204/"
  + "chrome-linux64/chrome";
// A URL vem por argumento: deixá-la fixa no código fez este teste rodar
// contra um endereço que tinha mudado e reprovar 25 de 25 por 404, como se
// o site estivesse quebrado.
const SITE = process.env.SITE || "https://oxeeraassim.github.io/apuracao/";
const NOITE = Date.UTC(2026, 9, 25, 21, 0);

const modo = process.argv[2] || "tudo";
const N = parseInt(process.argv[3] || "25", 10);

const mediana = (v) => {
  const s = [...v].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
};
const pior = (v, q) => {
  const s = [...v].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(s.length * q))];
};
const kb = (b) => (b / 1024).toFixed(0) + " KB";
const mb = (b) => (b / 1048576).toFixed(1) + " MB";

/* Relógio da noite, para a página realmente trabalhar. */
const comRelogio = async (p, quando = NOITE) =>
  p.evaluateOnNewDocument((fixo) => {
    const D = Date, delta = fixo - D.now();
    window.Date = class extends D {
      constructor(...a) { if (!a.length) super(D.now() + delta); else super(...a); }
      static now() { return D.now() + delta; }
    };
  }, quando);

async function simultaneas(nav, n) {
  console.log(`\n${n} pessoas abrindo a página ao mesmo tempo`);
  console.log("-".repeat(68));

  const t0 = Date.now();
  const resultados = await Promise.all(Array.from({ length: n }, async (_, i) => {
    const p = await nav.newPage();
    const erros = [];
    p.on("pageerror", (e) => erros.push(e.message.slice(0, 60)));

    // transferSize vem zerado para recurso de outra origem sem
    // Timing-Allow-Origin, então o peso é medido pelo protocolo do
    // navegador, que vê os bytes que de fato passaram no fio.
    let bytesFio = 0;
    const cdp = await p.target().createCDPSession();
    await cdp.send("Network.enable");
    // Todas as abas deste teste dividem o cache do navegador, então só a
    // primeira baixava de verdade e a mediana do peso dava 2 KB. Cada aba
    // aqui representa UMA PESSOA diferente, que nunca visitou o site: o
    // cache precisa estar desligado para o número significar algo.
    await p.setCacheEnabled(false);
    cdp.on("Network.loadingFinished", (e) => { bytesFio += e.encodedDataLength || 0; });

    const inicio = Date.now();
    try {
      await p.goto(SITE, { waitUntil: "load", timeout: 120000 });
    } catch (e) {
      await p.close();
      return { ok: false, erro: "não carregou: " + e.message.slice(0, 40) };
    }
    const carga = Date.now() - inicio;
    // Com o cache desligado e dezenas de abas disputando a rede, o mapa
    // (34 KB) chega depois do resto. Três segundos reprovavam visitas que
    // estavam só terminando de desenhar — impaciência do teste, não defeito
    // do site.
    await new Promise((r) => setTimeout(r, 8000));
    const m = await p.evaluate(() => {
      const rs = performance.getEntriesByType("resource");
      const proprios = rs.filter((r) => !r.name.includes("wikipedia"));
      return {
        arquivos: proprios.length,
        pintou: (performance.getEntriesByName("first-contentful-paint")[0] || {}).startTime || 0,
        paths: document.querySelectorAll("#mapa path").length,
        mapaOk: document.querySelectorAll("#mapa path").length === 27,
        relogioOk: !document.getElementById("contagem").hidden,
      };
    }).catch(() => null);
    await p.close();
    return { ok: !!m && m.mapaOk, carga, erros, bytes: bytesFio,
             erro: !m ? "página não respondeu"
                   : !m.mapaOk ? `mapa com ${m.paths} estados (esperado 27)` : null,
             ...(m || {}) };
  }));

  const bons = resultados.filter((r) => r.ok);
  const ruins = resultados.filter((r) => !r.ok);
  const cargas = bons.map((r) => r.carga);
  const bytes = bons.map((r) => r.bytes);

  console.log(`  carregaram certo ..... ${bons.length}/${n}`);
  console.log(`  tempo total .......... ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  if (bons.length) {
    console.log(`  carga mediana ........ ${mediana(cargas)} ms`);
    console.log(`  carga no pior 10% .... ${pior(cargas, 0.9)} ms`);
    console.log(`  primeiro desenho ..... ${Math.round(mediana(bons.map((r) => r.pintou)))} ms`);
    console.log(`  peso por visita ...... ${kb(mediana(bytes))} em ${mediana(bons.map((r) => r.arquivos))} arquivos`);
    console.log(`  mapa completo ........ ${bons.filter((r) => r.mapaOk).length}/${bons.length}`);
  }
  ruins.slice(0, 3).forEach((r) => console.log(`  ✗ ${r.erro || "falhou"}`));

  const erros = bons.flatMap((r) => r.erros || []);
  if (erros.length) console.log(`  ✗ ${erros.length} erro(s) de JS: ${erros[0]}`);

  // O que isso significa lá fora.
  if (bons.length) {
    const peso = mediana(bytes);
    console.log("\n  projetando para a noite real:");
    for (const gente of [1000, 10000, 50000]) {
      const banda = (peso * gente) / 1048576;
      // Metade das abas costuma estar em segundo plano, e aba escondida não
      // busca nada. O intervalo médio é 25s (varia ±20% por aparelho).
      const req = Math.round((gente * 0.5 * 54) / 25);
      console.log(`    ${String(gente).padStart(6)} pessoas → ${banda.toFixed(0)} MB`
        + ` na primeira visita · ~${req.toLocaleString("pt-BR")} req/s ao TSE`);
    }
    console.log("    (metade das abas em segundo plano não busca nada)");
  }
  return ruins.length === 0 && bons.every((r) => !(r.erros || []).length);
}

async function longa(nav) {
  console.log("\nUma aba aberta a noite inteira (tempo acelerado)");
  console.log("-".repeat(68));

  const p = await nav.newPage();
  const erros = [];
  p.on("pageerror", (e) => erros.push(e.message.slice(0, 70)));
  await comRelogio(p);
  await p.goto(SITE, { waitUntil: "networkidle2", timeout: 90000 });

  // Acelera o relógio interno da página: cada tick de 25s vira um de 300ms,
  // então quatro minutos de teste valem por umas seis horas de apuração.
  await p.evaluate(() => {
    const original = window.setTimeout;
    window.setTimeout = (fn, ms, ...a) =>
      original(fn, ms > 5000 ? 300 : ms, ...a);
  });

  const medir = () => p.evaluate(() => ({
    heap: performance.memory ? performance.memory.usedJSHeapSize : 0,
    nos: document.getElementsByTagName("*").length,
    ouvintes: (window.__contaTicks || 0),
  }));

  await new Promise((r) => setTimeout(r, 8000));
  const antes = await medir();
  const amostras = [];
  for (let i = 0; i < 8; i++) {
    await new Promise((r) => setTimeout(r, 15000));
    amostras.push(await medir());
    process.stdout.write(".");
  }
  console.log("");
  const depois = amostras[amostras.length - 1];

  const cresceu = depois.heap - antes.heap;
  const nosExtra = depois.nos - antes.nos;
  console.log(`  memória no início .... ${mb(antes.heap)}`);
  console.log(`  memória no fim ....... ${mb(depois.heap)}  (${cresceu >= 0 ? "+" : ""}${mb(cresceu)})`);
  console.log(`  nós na página ........ ${antes.nos} → ${depois.nos}  (${nosExtra >= 0 ? "+" : ""}${nosExtra})`);
  console.log(`  erros de JS .......... ${erros.length || "nenhum"}`);
  erros.slice(0, 3).forEach((e) => console.log(`    ✗ ${e}`));

  // Critério: a página redesenha a cada atualização, então algum vaivém é
  // normal. O que não pode é crescer sem parar.
  const ruim = [];
  if (antes.heap && cresceu > 25 * 1048576) ruim.push(`memória subiu ${mb(cresceu)}`);
  if (nosExtra > 400) ruim.push(`a página ganhou ${nosExtra} nós e não devolveu`);
  if (erros.length) ruim.push(`${erros.length} erro(s) de JS`);

  const vivo = await p.evaluate(() => {
    const b = [...document.querySelectorAll(".aba")].find((x) => x.dataset.aba === "pesquisas");
    if (b) b.click();
    return !!b;
  }).catch(() => false);
  console.log(`  ainda responde ....... ${vivo ? "sim ✓" : "NÃO ✗"}`);
  if (!vivo) ruim.push("a página parou de responder");

  await p.close();
  ruim.forEach((x) => console.log(`  ✗ ${x}`));
  return ruim.length === 0;
}

const nav = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--js-flags=--expose-gc"],
});

console.log(`\nCarga e resistência — ${SITE}\n${"=".repeat(68)}`);
let ok = true;
if (modo === "tudo" || modo === "simultaneas") ok = (await simultaneas(nav, N)) && ok;
if (modo === "tudo" || modo === "longa") ok = (await longa(nav)) && ok;
await nav.close();

console.log(`\n${"=".repeat(68)}`);
console.log(ok ? "passou" : "achados acima");
process.exit(ok ? 0 : 1);
