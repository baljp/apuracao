/*
 * Aba de pesquisas: coleta, cruzamento com o registro do TSE e agregação.
 *
 * De onde vêm os números. O TSE registra toda pesquisa eleitoral divulgada —
 * empresa, protocolo, contratante, quem pagou, tamanho da amostra,
 * metodologia — mas NÃO publica os percentuais dos candidatos. Então os
 * números vêm da tabela da Wikipédia (licença livre, atualizada em minutos por
 * uma comunidade grande), e o registro oficial do TSE entra como validação: é
 * ele que confirma que aquela pesquisa existe, sob qual protocolo e com que
 * amostra.
 *
 * Tudo roda no navegador de quem está vendo, como no resto do site. A API da
 * Wikipédia aceita requisições de qualquer origem.
 *
 * A agregação pondera cada pesquisa por três coisas:
 *   recência      — meia-vida de 4 dias; uma pesquisa de duas semanas atrás
 *                   pesa pouco contra uma de ontem
 *   amostra       — pela raiz do tamanho, que é como o erro amostral cai
 *   casa própria  — pesquisa contratada pela própria campanha pesa metade
 *
 * O que ela NÃO faz: corrigir o viés de cada instituto. A tentação é grande,
 * porque no 1º turno de 2026 as pesquisas erraram de forma sistemática. Mas
 * corrigir viés com uma única eleição de referência é ajustar ao ruído. O que
 * o site faz é mostrar o erro de cada instituto naquele turno, ao lado do
 * número atual, e deixar quem lê tirar a conclusão.
 */

const WIKI = "https://pt.wikipedia.org/w/api.php";
const PAGINA = "Pesquisas de opinião para a eleição presidencial no Brasil em 2026";

const MESES = {
  jan: 0, fev: 1, mar: 2, abr: 3, mai: 4, jun: 5,
  jul: 6, ago: 7, set: 8, out: 9, nov: 10, dez: 11,
};

// Resultado real do 1º turno, entre os dois que foram ao 2º (votos válidos
// sobre o total nominal). Serve para medir quanto cada instituto errou.
export const REAL_1T = { pl: 47.03, pt: 45.16 };

async function api(params) {
  const q = new URLSearchParams({ format: "json", origin: "*", ...params });
  const r = await fetch(WIKI + "?" + q.toString(), { cache: "no-store" });
  if (!r.ok) throw new Error("Wikipédia respondeu " + r.status);
  return r.json();
}

function numero(txt) {
  if (!txt) return null;
  const m = String(txt).replace(/\s/g, "").match(/(\d{1,3}(?:[.,]\d+)?)%?/);
  if (!m) return null;
  const v = parseFloat(m[1].replace(",", "."));
  return isFinite(v) ? v : null;
}

function inteiro(txt) {
  if (!txt) return null;
  const limpo = String(txt).replace(/[^\d]/g, "");
  return limpo ? parseInt(limpo, 10) : null;
}

/* "12 Out – 16 Out" ou "30 Set – 2 Out" -> data final, como Date. */
function dataFinal(txt, ano = 2026) {
  if (!txt) return null;
  const partes = String(txt).split(/[–—-]/);
  const ultima = partes[partes.length - 1].trim();
  const m = ultima.match(/(\d{1,2})\s*(?:de\s*)?([A-Za-zçÇ]{3,})/i);
  if (!m) return null;
  const mes = MESES[m[2].slice(0, 3).toLowerCase()];
  if (mes === undefined) return null;
  return new Date(Date.UTC(ano, mes, parseInt(m[1], 10)));
}

/* Acha a seção certa da página e devolve o HTML dela. */
async function htmlDaSecao(regexTitulo) {
  const secoes = (await api({ action: "parse", page: PAGINA, prop: "sections" }))
    .parse.sections;
  const sec = secoes.find((s) => regexTitulo.test(s.line));
  if (!sec) throw new Error("não achei a seção na Wikipédia");
  const r = await api({ action: "parse", page: PAGINA, prop: "text",
                        section: sec.index });
  return r.parse.text["*"];
}

function tabelas(html) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return [...doc.querySelectorAll("table")];
}

function linhasDe(tabela) {
  return [...tabela.querySelectorAll("tr")].map((tr) =>
    [...tr.children].map((c) => c.textContent.trim().replace(/\s+/g, " ")));
}

/* Pesquisas do 2º turno. Colunas da tabela:
   instituto | datas | amostra | margem | Lula | Flávio | indecisos | vantagem */
export async function buscarSegundoTurno() {
  const html = await htmlDaSecao(/Lula e Fl.vio/i);
  const tabs = tabelas(html);
  // A primeira tabela da seção é a dos agregadores; a segunda é a das
  // pesquisas em si.
  const tab = tabs.length > 1 ? tabs[1] : tabs[0];

  const saida = [];
  for (const l of linhasDe(tab)) {
    if (l.length < 6) continue;
    const pt = numero(l[4]);
    const pl = numero(l[5]);
    if (pt == null || pl == null) continue;       // ainda não divulgada
    if (pt + pl < 50 || pt + pl > 150) continue;  // linha que não é pesquisa
    const fim = dataFinal(l[1]);
    if (!fim) continue;

    // A Wikipédia é aberta a qualquer editor, então nada que venha dela entra
    // sem conferência. Aqui vão os limites de sanidade; o escape de HTML
    // acontece na hora de exibir, na página.
    const amostra = inteiro(l[2]);
    if (amostra != null && (amostra < 100 || amostra > 500000)) continue;
    if (+fim > Date.now() + 7 * 86400000) continue;  // pesquisa "do futuro"
    if (+fim < Date.UTC(2026, 9, 1)) continue;       // velha demais para o 2º turno

    saida.push({
      instituto: l[0].replace(/\[\d+\]/g, "").trim().slice(0, 60),
      periodo: String(l[1]).slice(0, 40),
      fim,
      amostra,
      margem: numero(l[3]),
      pt, pl,
      // Percentuais sobre votos válidos, para comparar maçã com maçã: cada
      // pesquisa trata brancos, nulos e indecisos de um jeito.
      validosPl: (100 * pl) / (pl + pt),
    });
  }
  saida.sort((a, b) => b.fim - a.fim);
  return saida;
}

/* Pesquisas finais do 1º turno, para medir o erro de cada instituto. */
export async function buscarPrimeiroTurno() {
  let html;
  try {
    html = await htmlDaSecao(/^Outubro$/i);
  } catch {
    return [];
  }
  const tab = tabelas(html)[0];
  if (!tab) return [];

  const linhas = linhasDe(tab);
  const cab = (linhas[0] || []).concat(linhas[1] || []).join(" ");
  // Descobre em que coluna estão os dois finalistas, já que a tabela do 1º
  // turno tem uma coluna por candidato.
  const saida = [];
  for (const l of linhas) {
    if (l.length < 6) continue;
    const fim = dataFinal(l[1]);
    if (!fim) continue;
    const nums = l.slice(4).map(numero).filter((v) => v != null && v <= 100);
    if (nums.length < 2) continue;
    saida.push({ instituto: l[0].replace(/\[\d+\]/g, "").trim(), fim, nums,
                 amostra: inteiro(l[2]) });
  }
  return saida;
}

/**
 * Agrega as pesquisas numa estimativa só.
 * Devolve o percentual do finalista do PL sobre votos válidos, com a faixa.
 */
export function agregar(pesquisas, { meiaVidaDias = 4, agora = new Date() } = {}) {
  if (!pesquisas.length) return null;

  const usadas = [];
  let somaPeso = 0, soma = 0;

  for (const p of pesquisas) {
    const dias = Math.max(0, (agora - p.fim) / 86400000);
    if (dias > 21) continue;                        // mais velha que três semanas
    const peso = Math.pow(0.5, dias / meiaVidaDias)
               * Math.sqrt(Math.min(p.amostra || 1000, 10000) / 1000);
    somaPeso += peso;
    soma += peso * p.validosPl;
    usadas.push({ ...p, peso, dias });
  }
  if (!somaPeso) return null;

  const media = soma / somaPeso;

  // Dispersão entre as pesquisas: é ela, e não a margem declarada de cada
  // uma, que mostra o desacordo real entre os institutos.
  let varSoma = 0;
  for (const u of usadas) varSoma += u.peso * Math.pow(u.validosPl - media, 2);
  const desvio = Math.sqrt(varSoma / somaPeso);

  // Peso efetivo (Kish): quantas pesquisas "de verdade" a média representa.
  let somaQuad = 0;
  for (const u of usadas) somaQuad += u.peso * u.peso;
  const nEfetivo = (somaPeso * somaPeso) / somaQuad;

  // O erro de uma média de pesquisas não cai com a raiz do número delas: os
  // institutos erram juntos, porque partilham premissas sobre quem vota. Por
  // isso somamos um piso de erro comum, que nenhuma quantidade de pesquisas
  // elimina. 1,5 ponto é a ordem de grandeza do erro observado no 1º turno
  // de 2026.
  const PISO_ERRO_COMUM = 1.5;
  const erro = Math.sqrt(
    Math.pow(desvio / Math.sqrt(Math.max(nEfetivo, 1)), 2) +
    Math.pow(PISO_ERRO_COMUM, 2)
  );

  return {
    pl: media,
    pt: 100 - media,
    faixa: [media - 1.64 * erro, media + 1.64 * erro],
    erro,
    desvio,
    nUsadas: usadas.length,
    nEfetivo,
    maisRecente: usadas[0] ? usadas[0].fim : null,
    usadas,
  };
}

/**
 * Cruza as pesquisas com o registro oficial do TSE, que é servido como um
 * arquivo gerado por programa/coletar_registro_tse.py. Marca cada pesquisa
 * como registrada (com protocolo) ou não encontrada.
 */
export async function cruzarComTSE(pesquisas) {
  let registro = null;
  try {
    const r = await fetch("./registro-tse.json", { cache: "force-cache" });
    if (r.ok) registro = await r.json();
  } catch { /* o site funciona sem isso */ }
  if (!registro || !registro.pesquisas) return pesquisas;

  const normal = (s) => (s || "").toUpperCase()
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^A-Z0-9]/g, "");

  for (const p of pesquisas) {
    const alvo = normal(p.instituto);
    const achado = registro.pesquisas.find((r) => {
      const nome = normal(r.empresa);
      if (!nome || !alvo) return false;
      const bate = nome.includes(alvo) || alvo.includes(nome);
      if (!bate) return false;
      // Mesma amostra é uma confirmação forte.
      return !p.amostra || !r.amostra || Math.abs(p.amostra - r.amostra) < 2;
    });
    if (achado) {
      p.tse = { protocolo: achado.protocolo, contratante: achado.contratante,
                amostra: achado.amostra };
    }
  }
  return pesquisas;
}
