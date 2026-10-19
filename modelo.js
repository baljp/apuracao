/*
 * O modelo de projeção — mesma lógica da versão em Python (modelo.py).
 *
 * A ideia em uma frase: o percentual bruto que o TSE mostra no começo da noite
 * não é errado, é uma amostra enviesada — vem desproporcionalmente do Sul e do
 * Centro-Oeste, que apuram rápido, e quase nada do Nordeste, que demora. O
 * modelo calcula quanto a parte já apurada DEVERIA dar se o eleitorado
 * repetisse o 1º turno, mede a diferença contra o que saiu da urna, e aplica
 * essa diferença ao que falta.
 *
 * Os quatro passos estão comentados abaixo, em ordem.
 */

export const REGIAO = {
  ac:"norte", am:"norte", ap:"norte", pa:"norte", ro:"norte", rr:"norte", to:"norte",
  al:"nordeste", ba:"nordeste", ce:"nordeste", ma:"nordeste", pb:"nordeste",
  pe:"nordeste", pi:"nordeste", rn:"nordeste", se:"nordeste",
  df:"centro-oeste", go:"centro-oeste", ms:"centro-oeste", mt:"centro-oeste",
  es:"sudeste", mg:"sudeste", rj:"sudeste", sp:"sudeste",
  pr:"sul", rs:"sul", sc:"sul",
  zz:"exterior",
};

// Parâmetros do encolhimento. "Quantos votos de informação valem o prior":
// com pouca apuração o prior manda, com muita o dado local manda.
// Calibrados no backtest contra o 2º turno de 2022.
const K_UF = 180000;
const K_REGIAO = 90000;
const SIGMA_SWING = 0.035;
const MIN_VOTOS_SWING = 400;
const LAMBDA_PERFIL = 0.015;

const logit = (a, b) => Math.log(Math.max(a, 0.5) / Math.max(b, 0.5));

function share(x) {
  if (x > 30) return 1;
  if (x < -30) return 0;
  return 1 / (1 + Math.exp(-x));
}

const encolher = (valor, peso, prior, k) => (peso * valor + k * prior) / (peso + k);

/* Gerador pseudoaleatório com semente, para que o bootstrap dê o mesmo
 * resultado a cada atualização e a margem não fique tremendo na tela. */
function rng(semente) {
  let s = semente >>> 0;
  return function () {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function normal(rand) {
  let u = 0, v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export class Modelo {
  constructor(base) {
    const n = base.ufs.length;
    this.n = n;
    this.uf = base.ufs;
    this.cd = base.cds;
    this.nm = base.nms;
    this.eleitorado = base.ele;

    // Base: votos válidos do 1º turno restritos aos dois finalistas.
    this.validosBase = new Float64Array(n);
    this.baseLogit = new Float64Array(n);
    // Perfil: quanto do voto do município foi para candidatos eliminados.
    // É o que permite notar que a transferência não foi igual em todo lugar.
    this.perfil = new Float64Array(n);
    this.fracao = new Float64Array(n);

    this.indicesPorUf = new Map();
    for (let i = 0; i < n; i++) {
      const pl = base.pl[i], pt = base.pt[i], out = base.out[i];
      this.validosBase[i] = pl + pt;
      this.baseLogit[i] = logit(pl, pt);
      const total = pl + pt + out;
      this.perfil[i] = total > 0 ? out / total : 0;
      if (!this.indicesPorUf.has(this.uf[i])) this.indicesPorUf.set(this.uf[i], []);
      this.indicesPorUf.get(this.uf[i]).push(i);
    }

    this.chave = new Array(n);
    this.porChave = new Map();
    for (let i = 0; i < n; i++) {
      this.chave[i] = this.uf[i] + "/" + this.cd[i];
      this.porChave.set(this.chave[i], i);
    }

    this.eleitoradoTotal = this.eleitorado.reduce((a, b) => a + b, 0);
    this.validosBaseTotal = this.validosBase.reduce((a, b) => a + b, 0);
  }

  /**
   * andamento: Map ou objeto {"uf/cd": fracao do eleitorado já totalizada}
   * observado: {uf: {pl, pt}} — votos já apurados no 2º turno
   */
  projetar(andamento, observado, nBootstrap = 300) {
    const pega = (k) => (andamento instanceof Map ? andamento.get(k) : andamento[k]) || 0;
    for (let i = 0; i < this.n; i++) {
      this.fracao[i] = Math.min(Math.max(pega(this.chave[i]), 0), 1);
    }

    /* --- passos 1 e 2: esperado composicional e swing por estado ---------
     * O "esperado" soma, município a município e só na fração já apurada, o
     * resultado que aquele pedaço teria dado no 1º turno. Se só o Sul apurou,
     * o esperado também é só do Sul — é isso que anula o viés geográfico.
     * O swing é a diferença, em log-odds, contra o que saiu da urna. */
    const swingUf = new Map();
    const pesoUf = new Map();
    const escalaUf = new Map();
    const pesoEscala = new Map();
    const detalhe = new Map();

    for (const [uf, idx] of this.indicesPorUf) {
      const obs = observado[uf] || {};
      const obsPl = obs.pl || 0, obsPt = obs.pt || 0;
      let espPl = 0, espPt = 0;
      for (const i of idx) {
        if (this.fracao[i] <= 0) continue;
        const s = share(this.baseLogit[i]);
        const v = this.fracao[i] * this.validosBase[i];
        espPl += v * s;
        espPt += v * (1 - s);
      }
      const votosObs = obsPl + obsPt;

      // Quanto voto válido o 2º turno está rendendo, comparado ao que o 1º
      // rendeu nos mesmos lugares.
      //
      // O modelo estima o que falta como "o mesmo volume de votos do 1º
      // turno". Se brancos, nulos e abstenções mudarem — e mudam, geralmente
      // crescendo mais onde o candidato eliminado era forte —, o peso de cada
      // município na soma nacional sai errado. Esta razão corrige a escala
      // com o que de fato saiu das urnas.
      const esperadoVotos = espPl + espPt;
      if (esperadoVotos > 0 && votosObs >= MIN_VOTOS_SWING) {
        escalaUf.set(uf, votosObs / esperadoVotos);
        pesoEscala.set(uf, votosObs);
      }

      if (votosObs >= MIN_VOTOS_SWING && espPl > 0 && espPt > 0) {
        swingUf.set(uf, logit(obsPl, obsPt) - logit(espPl, espPt));
        pesoUf.set(uf, votosObs);
      }
      detalhe.set(uf, { obsPl, obsPt, espPl, espPt });
    }

    /* --- passo 3: encolhimento nacional -> região -> estado --------------
     * Com 1% apurado o swing de um estado isolado é ruído, então ele é puxado
     * para o da sua região, e o da região para o nacional, com força inversa à
     * informação disponível. No início o modelo é quase nacional; conforme os
     * votos entram, vira estadual. É isso que o deixa estável desde cedo. */
    let pesoTotal = 0, somaPonderada = 0;
    for (const [uf, sw] of swingUf) {
      somaPonderada += sw * pesoUf.get(uf);
      pesoTotal += pesoUf.get(uf);
    }
    const swingNacional = pesoTotal > 0 ? somaPonderada / pesoTotal : 0;

    const acumRegiao = new Map();
    for (const [uf, sw] of swingUf) {
      const r = REGIAO[uf] || "outros";
      const a = acumRegiao.get(r) || [0, 0];
      a[0] += sw * pesoUf.get(uf);
      a[1] += pesoUf.get(uf);
      acumRegiao.set(r, a);
    }
    const swingRegiao = new Map();
    for (const [r, [soma, peso]] of acumRegiao) {
      const bruto = peso > 0 ? soma / peso : swingNacional;
      swingRegiao.set(r, encolher(bruto, peso, swingNacional, K_REGIAO));
    }

    const swingFinal = new Map();
    for (const uf of this.indicesPorUf.keys()) {
      const prior = swingRegiao.get(REGIAO[uf] || "outros") ?? swingNacional;
      swingFinal.set(uf, swingUf.has(uf)
        ? encolher(swingUf.get(uf), pesoUf.get(uf), prior, K_UF)
        : prior);
    }

    // A escala de votos válidos segue o mesmo encolhimento do swing: com
    // pouca apuração num estado, vale a escala nacional.
    let pesoEscTotal = 0, somaEsc = 0;
    for (const [uf, e] of escalaUf) {
      somaEsc += e * pesoEscala.get(uf);
      pesoEscTotal += pesoEscala.get(uf);
    }
    const escalaNacional = pesoEscTotal > 0 ? somaEsc / pesoEscTotal : 1;
    const escalaFinal = new Map();
    for (const uf of this.indicesPorUf.keys()) {
      const e = escalaUf.has(uf)
        ? encolher(escalaUf.get(uf), pesoEscala.get(uf), escalaNacional, K_UF)
        : escalaNacional;
      // Fora desta faixa é sinal de dado estranho, não de mudança real de
      // comparecimento.
      escalaFinal.set(uf, Math.min(Math.max(e, 0.75), 1.25));
    }

    const bPerfil = this._coefPerfil(swingUf, pesoUf);

    /* --- passo 4: projeção e margem -------------------------------------- */
    const central = this._somar(swingFinal, observado, null, bPerfil, escalaFinal);
    const faixa = this._bootstrap(swingFinal, observado, nBootstrap, bPerfil, escalaFinal);

    let eleitoradoApurado = 0, votosApurados = 0, somaObsPl = 0;
    for (let i = 0; i < this.n; i++) eleitoradoApurado += this.fracao[i] * this.eleitorado[i];
    for (const d of detalhe.values()) {
      votosApurados += d.obsPl + d.obsPt;
      somaObsPl += d.obsPl;
    }

    const estados = [];
    for (const [uf, idx] of this.indicesPorUf) {
      const d = detalhe.get(uf);
      const o = d.obsPl + d.obsPt;
      let elei = 0, apu = 0;
      for (const i of idx) { elei += this.eleitorado[i]; apu += this.fracao[i] * this.eleitorado[i]; }
      estados.push({
        uf: uf.toUpperCase(),
        regiao: REGIAO[uf] || "outros",
        pctApurado: elei ? (100 * apu) / elei : 0,
        obsPl: o ? (100 * d.obsPl) / o : null,
        projPl: central.porUf.get(uf).pctPl,
        swing: swingFinal.get(uf),
      });
    }
    estados.sort((a, b) => b.pctApurado - a.pctApurado);

    return {
      pctApurado: this.eleitoradoTotal ? (100 * eleitoradoApurado) / this.eleitoradoTotal : 0,
      votosApurados,
      brutoPl: votosApurados ? (100 * somaObsPl) / votosApurados : null,
      projecaoPl: central.pctPl,
      projecaoPt: 100 - central.pctPl,
      faixaPl: faixa.faixa,
      probPl: faixa.probPl,
      swingNacional,
      estados,
    };
  }

  /* Quanto o swing varia com o perfil do município, estimado a partir da
   * variação entre estados. A regularização é o que impede o coeficiente de
   * perseguir ruído, já que são no máximo 27 pontos. */
  _coefPerfil(swingUf, pesoUf) {
    if (swingUf.size < 6) return 0;
    const pontos = [];
    for (const [uf, sw] of swingUf) {
      const idx = this.indicesPorUf.get(uf) || [];
      let base = 0, soma = 0;
      for (const i of idx) { base += this.validosBase[i]; soma += this.perfil[i] * this.validosBase[i]; }
      if (base > 0) pontos.push([soma / base, sw, pesoUf.get(uf)]);
    }
    if (pontos.length < 6) return 0;
    let pesoTotal = 0, xm = 0, ym = 0;
    for (const p of pontos) pesoTotal += p[2];
    if (pesoTotal <= 0) return 0;
    for (const p of pontos) { xm += (p[0] * p[2]) / pesoTotal; ym += (p[1] * p[2]) / pesoTotal; }
    let num = 0, den = 0;
    for (const p of pontos) {
      num += p[2] * (p[0] - xm) * (p[1] - ym);
      den += p[2] * (p[0] - xm) ** 2;
    }
    return num / (den + LAMBDA_PERFIL * pesoTotal);
  }

  /* O que já apurou entra como veio da urna (é real); o que falta recebe a
   * base do município mais o swing que lhe cabe. */
  _somar(swingFinal, observado, ruido, bPerfil, escala) {
    let totalPl = 0, totalPt = 0;
    const porUf = new Map();

    for (const [uf, idx] of this.indicesPorUf) {
      const obs = observado[uf] || {};
      let pl = obs.pl || 0, pt = obs.pt || 0;
      let sw = swingFinal.get(uf) || 0;
      if (ruido) sw += ruido.get(uf) || 0;

      let perfilApurado = null;
      if (bPerfil) {
        let peso = 0, soma = 0;
        for (const i of idx) {
          const w = this.fracao[i] * this.validosBase[i];
          peso += w; soma += this.perfil[i] * w;
        }
        if (peso > 0) perfilApurado = soma / peso;
      }

      // O volume do que falta é corrigido pelo que o 2º turno está rendendo
      // de voto válido naquele estado.
      const fator = (escala && escala.get(uf)) || 1;

      for (const i of idx) {
        const falta = 1 - this.fracao[i];
        if (falta <= 1e-9) continue;
        let swM = sw;
        if (perfilApurado !== null) swM += bPerfil * (this.perfil[i] - perfilApurado);
        const s = share(this.baseLogit[i] + swM);
        const v = falta * this.validosBase[i] * fator;
        pl += v * s;
        pt += v * (1 - s);
      }
      const soma = pl + pt;
      porUf.set(uf, { pl, pt, pctPl: soma ? (100 * pl) / soma : 50 });
      totalPl += pl; totalPt += pt;
    }
    const soma = totalPl + totalPt;
    return { pl: totalPl, pt: totalPt, pctPl: soma ? (100 * totalPl) / soma : 50, porUf };
  }

  /* Margem de 90%: o swing é perturbado por um termo comum a todos os estados
   * (erro nacional, que não some com mais apuração) e um termo próprio de cada
   * um. A escala encolhe conforme menos resta a apurar. */
  _bootstrap(swingFinal, observado, n, bPerfil, escala) {
    const central = this._somar(swingFinal, observado, null, bPerfil, escala).pctPl;
    if (n <= 0) return { faixa: [central, central], probPl: central > 50 ? 1 : 0 };

    let falta = 0;
    for (let i = 0; i < this.n; i++) falta += (1 - this.fracao[i]) * this.validosBase[i];
    const fracFalta = this.validosBaseTotal ? falta / this.validosBaseTotal : 1;
    // sigma, e não "escala": o parâmetro escala é outra coisa (o fator de
    // votos válidos por UF). Confundir os dois foi exatamente o bug que
    // apagava a correção dentro do bootstrap no lado Python.
    const sigma = SIGMA_SWING * Math.sqrt(Math.max(fracFalta, 0));

    const rand = rng(12345);
    const ufs = [...this.indicesPorUf.keys()];
    const amostras = [];
    for (let k = 0; k < n; k++) {
      const comum = normal(rand) * sigma * 0.75;
      const ruido = new Map();
      for (const u of ufs) ruido.set(u, comum + normal(rand) * sigma * 0.6);
      amostras.push(this._somar(swingFinal, observado, ruido, bPerfil, escala).pctPl);
    }
    amostras.sort((a, b) => a - b);
    return {
      faixa: [amostras[Math.floor(0.05 * (n - 1))], amostras[Math.floor(0.95 * (n - 1))]],
      probPl: amostras.filter((a) => a > 50).length / n,
    };
  }
}
