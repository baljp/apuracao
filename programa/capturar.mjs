/*
 * Tira fotos do site, para conferir o desenho sem depender de publicar.
 *
 * Captura em largura de celular, que é onde a maioria vai ver, e também em
 * desktop. Usa o modo de ensaio (?demo=N) para que as telas mostrem uma
 * apuração em andamento, e não a tela vazia de quem abre antes do domingo.
 *
 * Uso:  node programa/capturar.mjs [porta]
 */

import puppeteer from "puppeteer-core";
import { mkdirSync } from "node:fs";

const PORTA = process.argv[2] || "8899";
const BASE = `http://localhost:${PORTA}/`;
const CHROME = "/root/.cache/puppeteer/chrome/linux-131.0.6778.204/"
  + "chrome-linux64/chrome";

const SAIDA = "/home/claude/apuracao-2026/capturas";
mkdirSync(SAIDA, { recursive: true });

const telas = [
  { nome: "celular-apuracao", url: "?demo=12", w: 390, h: 1400, aba: null },
  { nome: "celular-pesquisas", url: "?demo=12", w: 390, h: 1500, aba: "pesquisas" },
  { nome: "celular-inicio", url: "", w: 390, h: 1000, aba: null },
  { nome: "desktop-apuracao", url: "?demo=12", w: 1100, h: 1500, aba: null },
];

const navegador = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

for (const t of telas) {
  const pag = await navegador.newPage();
  await pag.setViewport({ width: t.w, height: t.h, deviceScaleFactor: 2 });
  await pag.goto(BASE + t.url, { waitUntil: "networkidle2", timeout: 60000 });
  // Dá tempo de o modelo rodar e o mapa chegar.
  await new Promise((r) => setTimeout(r, 4500));
  if (t.aba) {
    await pag.evaluate((qual) => {
      const b = [...document.querySelectorAll(".aba")]
        .find((x) => x.dataset.aba === qual);
      if (b) b.click();
    }, t.aba);
    await new Promise((r) => setTimeout(r, 6000));
  }
  const arquivo = `${SAIDA}/${t.nome}.png`;
  await pag.screenshot({ path: arquivo, fullPage: true });
  const erros = await pag.evaluate(() =>
    document.getElementById("status")?.textContent || "");
  console.log(`  ${t.nome.padEnd(20)} ${t.w}px  ${erros.slice(0, 60)}`);
  await pag.close();
}

await navegador.close();
console.log(`\nCapturas em ${SAIDA}`);
