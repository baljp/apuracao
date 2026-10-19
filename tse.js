/*
 * Leitura dos arquivos públicos de divulgação do TSE, direto do navegador.
 *
 * O TSE serve esses arquivos com CORS liberado, então o site não precisa de
 * servidor nem de proxy: o navegador de quem está vendo busca os dados na
 * fonte oficial. Por isso ele funciona hospedado em qualquer lugar estático,
 * inclusive GitHub Pages, e aguenta qualquer número de visitantes.
 *
 * São 27 arquivos de resultado (um por estado) + 27 de andamento por leitura.
 */

const BASE = "https://resultados.tse.jus.br/oficial";
const CICLO = "ele2026";

export const ELEICAO_1T = 6257;  // Federal 2026, 1º turno
export const ELEICAO_2T = 6258;  // Federal 2026, 2º turno
export const NUM_PL = "22";
export const NUM_PT = "13";

export const UFS = ["ac","al","am","ap","ba","ce","df","es","go","ma","mg","ms",
  "mt","pa","pb","pe","pi","pr","rj","rn","ro","rr","rs","sc","se","sp","to","zz"];

const cod = (n) => "e" + String(n).padStart(6, "0");

const urlResultado = (eleicao, uf) =>
  `${BASE}/${CICLO}/${eleicao}/dados/${uf}/${uf}-c0001-${cod(eleicao)}-u.json`;

const urlAndamento = (eleicao, uf) =>
  `${BASE}/${CICLO}/${eleicao}/dados/${uf}/${uf}-${cod(eleicao)}-ab.json`;

function num(txt) {
  if (txt === undefined || txt === null || txt === "") return 0;
  const s = String(txt);
  return s.includes(",")
    ? parseFloat(s.replace(/\./g, "").replace(",", "."))
    : parseFloat(s);
}

async function buscar(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/* Roda as tarefas com um teto de simultâneas, para não abrir 54 conexões de
 * uma vez e engasgar o navegador (e o celular de quem está vendo). */
async function emLotes(itens, trabalho, simultaneas = 8) {
  const saida = new Array(itens.length);
  let proximo = 0;
  const operarios = Array.from({ length: Math.min(simultaneas, itens.length) }, async () => {
    while (true) {
      const i = proximo++;
      if (i >= itens.length) break;
      saida[i] = await trabalho(itens[i]);
    }
  });
  await Promise.all(operarios);
  return saida;
}

export async function lerResultados(eleicao) {
  const observado = {};
  const nomes = {};
  const falhas = [];
  // Além dos votos dos dois finalistas, o arquivo traz brancos, nulos,
  // abstenção, comparecimento e seções — tudo o que o eleitor procura numa
  // noite de apuração, e que estava sendo ignorado.
  const totais = {
    brancos: 0, nulos: 0, abstencao: 0, comparecimento: 0,
    eleitorado: 0, secoes: 0, secoesApuradas: 0, validos: 0,
  };
  let horaTSE = "";

  await emLotes(UFS, async (uf) => {
    try {
      const doc = await buscar(urlResultado(eleicao, uf));
      let pl = 0, pt = 0;
      for (const cargo of doc.carg || [])
        for (const agr of cargo.agr || [])
          for (const par of agr.par || [])
            for (const c of par.cand || []) {
              if (c.n === NUM_PL) { pl += num(c.vap); nomes.pl = (c.nmu || "").toLowerCase(); }
              else if (c.n === NUM_PT) { pt += num(c.vap); nomes.pt = (c.nmu || "").toLowerCase(); }
            }
      observado[uf] = { pl, pt };

      const v = doc.v || {}, e = doc.e || {}, s = doc.s || {};
      totais.brancos += num(v.vb);
      totais.nulos += num(v.tvn);
      totais.validos += num(v.vv);
      totais.abstencao += num(e.a);
      totais.comparecimento += num(e.c);
      totais.eleitorado += num(e.te);
      totais.secoes += num(s.ts);
      totais.secoesApuradas += num(s.st);
      // Horário em que o TSE gerou o arquivo — mais fiel que a hora local
      // de quem está olhando.
      if (doc.ht && doc.ht > horaTSE) horaTSE = doc.ht;
    } catch (err) {
      falhas.push(uf);
    }
  });

  return { observado, nomes, falhas, totais, horaTSE };
}

export async function lerAndamento(eleicao) {
  const fracoes = new Map();
  const falhas = [];

  await emLotes(UFS, async (uf) => {
    try {
      const doc = await buscar(urlAndamento(eleicao, uf));
      for (const abr of doc.abr || []) {
        if (abr.tpabr !== "mun") continue;
        const e = abr.e || {};
        const total = num(e.te);
        const apurado = num(e.est);
        fracoes.set(`${uf}/${abr.cdabr}`, total > 0 ? apurado / total : 0);
      }
    } catch (e) {
      falhas.push(uf);
    }
  });

  return { fracoes, falhas };
}

export async function lerTudo(eleicao) {
  const [res, and] = await Promise.all([lerResultados(eleicao), lerAndamento(eleicao)]);
  return {
    observado: res.observado,
    fracoes: and.fracoes,
    nomes: res.nomes,
    totais: res.totais,
    horaTSE: res.horaTSE,
    falhas: [...new Set([...res.falhas, ...and.falhas])],
  };
}
