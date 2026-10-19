"""
O modelo de projeção.

A ideia em uma frase: o percentual bruto que o TSE mostra no começo da noite não
é errado, é apenas uma amostra enviesada — ela vem desproporcionalmente do Sul e
do Centro-Oeste, que apuram rápido, e quase nada do Nordeste, que apura devagar.
O modelo não tenta "adivinhar" o resultado: ele calcula quanto a parte já
apurada DEVERIA dar se o eleitorado repetisse exatamente o 1º turno, mede a
diferença entre isso e o que de fato saiu da urna, e aplica essa diferença ao
que falta.

Os quatro passos:

1. ESPERADO COMPOSICIONAL
   Para cada município sabemos quanto do seu eleitorado já foi totalizado
   (arquivo de andamento do TSE) e como ele votou no 1º turno (a base). Somando
   município a município, obtemos o resultado que a parcela já apurada teria
   dado no 1º turno. É isso que neutraliza o viés geográfico: se só o Sul
   apurou, o "esperado" também é só do Sul.

2. SWING
   A diferença, em log-odds, entre o que saiu da urna e esse esperado. O swing
   é o que realmente mudou entre os dois turnos — inclui para onde foram os
   votos dos candidatos eliminados, mudanças de comparecimento e de humor do
   eleitorado. É uma quantidade pequena e estável, muito mais fácil de estimar
   do que o resultado em si.

3. ENCOLHIMENTO HIERÁRQUICO
   Com 1% apurado, o swing de um estado isolado é puro ruído. Então o swing de
   cada UF é puxado na direção do swing da sua região, e o da região na direção
   do swing nacional, com força inversamente proporcional à informação
   disponível. No começo da noite o modelo é quase nacional; conforme os votos
   entram, ele se torna estadual. É isso que o deixa estável desde o início.

4. PROJEÇÃO E MARGEM
   O que falta em cada município recebe a base do município mais o swing que lhe
   cabe. A margem vem de um bootstrap que reamostra os municípios e perturba o
   swing, com a escala calibrada no backtest.
"""

from __future__ import annotations

import math
import random

import tse

# --- parâmetros do encolhimento -------------------------------------------
# k é "quantos votos de informação valem o prior". Com poucos votos apurados o
# prior domina; com muitos, o dado local domina. Calibrados em backtest.py.
K_UF = 180_000.0
K_REGIAO = 90_000.0

# Dispersão do swing entre UFs usada no bootstrap, também calibrada.
SIGMA_SWING = 0.035

MIN_VOTOS_SWING = 400  # abaixo disso o swing de uma UF é só ruído

# Âncora das pesquisas.
#
# Com pouquíssima apuração, o modelo precisa de algum palpite sobre para onde
# o país se moveu entre os turnos. Sem âncora, ele parte de "nada mudou" e vai
# descobrindo o swing conforme os votos chegam — o que funciona bem quando a
# mudança é parecida em todo lugar (2022), mas atrasa quando ela é muito
# desigual entre regiões (2018), porque as regiões que apuram primeiro não
# representam as que faltam.
#
# A âncora é o swing que as pesquisas finais sugerem. K_PRIOR diz quantos
# votos apurados valem o mesmo que ela: passado esse volume, o dado real
# manda e as pesquisas somem da conta. É deliberadamente baixo, porque as
# pesquisas erram — em 2022 elas apontavam cerca de 2 pontos para o lado
# errado, e em 2026 erraram o líder do 1º turno.
K_PRIOR = 1_500_000

# Regressão do swing sobre o perfil do município (quanto do voto do 1º turno
# foi para candidatos eliminados). Onde havia muito voto de terceiro, o swing
# tende a ser diferente, porque esse eleitorado precisou escolher de novo.
# LAMBDA é a regularização: com 27 estados, sem ela a regressão viraria ruído.
USAR_REGRESSAO_PERFIL = True
LAMBDA_PERFIL = 0.015

# Regressão do swing sobre o NÍVEL do lugar — TESTADA E DESCARTADA.
#
# A hipótese era boa. Em 2018 o swing não foi parecido pelo país: onde
# Bolsonaro era forte no 1º turno ele caiu muito (Sudeste, 73,5% -> -8,1
# pontos) e onde era fraco caiu pouco (Nordeste, 33,8% -> -3,5). O swing era
# função do nível, e medindo essa inclinação o modelo poderia inferir o
# Nordeste a partir do Sul, em vez de copiar um no outro.
#
# Só que não funciona. Testado em 15 combinações de λ e limite (ver
# testar_nivel.py), piora em TODAS: o pior caso sobe de 1,98 para 2,18 pp, e
# quanto mais solto o coeficiente, pior fica.
#
# O motivo é instrutivo. Com tudo apurado, a inclinação verdadeira de 2018 é
# -0,140. Mas no início da noite ela não pode ser medida: os estados que
# apuram primeiro são justamente os de nível alto, e a parcela apurada deles
# ainda não os representa. A reta ajustada ali mistura o padrão real com o
# viés de composição, e depois é extrapolada para fora da amostra, justo nos
# estados sobre os quais não há informação. Amplificar uma estimativa ruim na
# direção de quem não apurou é pior do que não fazer nada.
#
# Fica desligada. O código permanece porque o experimento negativo é parte do
# resultado: alguém que tiver a mesma ideia já sabe que ela foi tentada.
USAR_REGRESSAO_NIVEL = False
LAMBDA_NIVEL = 0.4
# Teto para o quanto a extrapolação pode mexer no swing de um lugar, em
# log-odds. Sem isso, um estado muito distante da média puxaria a conta para
# território que nenhum dado sustenta.
LIMITE_AJUSTE_NIVEL = 0.15


def _logit(a: float, b: float) -> float:
    """log(a/b), protegido contra zero."""
    a = max(a, 0.5)
    b = max(b, 0.5)
    return math.log(a / b)


def _share(x: float) -> float:
    """log-odds -> proporção."""
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _encolher(valor: float, peso: float, prior: float, k: float) -> float:
    return (peso * valor + k * prior) / (peso + k)


class Municipio:
    """Um município com sua base do 1º turno e seu andamento no 2º."""

    __slots__ = ("uf", "cd", "nm", "regiao", "eleitorado", "validos_base",
                 "base_logit", "perfil", "fracao", "peso_restante")

    def __init__(self, reg: dict):
        self.uf = reg["uf"]
        self.cd = reg["cd"]
        self.nm = reg["nm"]
        self.regiao = reg.get("regiao") or tse.REGIAO.get(reg["uf"], "outros")
        self.eleitorado = max(int(reg.get("eleitorado", 0)), 0)

        votos = reg.get("votos", {}) or {}
        v_pl = float(votos.get(tse.NUM_PL, 0))
        v_pt = float(votos.get(tse.NUM_PT, 0))
        outros = sum(float(v) for n, v in votos.items()
                     if n not in (tse.NUM_PL, tse.NUM_PT))

        # Votos válidos do 1º turno restritos aos dois finalistas: essa é a
        # base. Os eliminados não entram aqui, mas entram no perfil (abaixo),
        # porque é a presença deles que faz o swing variar entre municípios.
        self.validos_base = v_pl + v_pt
        self.base_logit = _logit(v_pl, v_pt)

        total = v_pl + v_pt + outros
        self.perfil = (outros / total) if total > 0 else 0.0

        self.fracao = 0.0        # fração do eleitorado já totalizada no 2º turno
        self.peso_restante = 0.0

    @property
    def chave(self) -> str:
        return "%s/%s" % (self.uf, self.cd)


class Modelo:
    def __init__(self, base: dict):
        self.municipios = [Municipio(m) for m in base["municipios"]
                           if m.get("eleitorado", 0) > 0 and
                           (float(m.get("votos", {}).get(tse.NUM_PL, 0)) +
                            float(m.get("votos", {}).get(tse.NUM_PT, 0))) > 0]
        self.por_chave = {m.chave: m for m in self.municipios}
        self.por_uf = {}
        for m in self.municipios:
            self.por_uf.setdefault(m.uf, []).append(m)

        self.validos_base_total = sum(m.validos_base for m in self.municipios)
        self.eleitorado_total = sum(m.eleitorado for m in self.municipios)

        # Perfil nacional de referência: a média do país, ponderada por voto.
        peso = sum(m.validos_base for m in self.municipios) or 1.0
        self.perfil_medio = sum(m.perfil * m.validos_base
                                for m in self.municipios) / peso

        # Nível nacional e por UF: a posição do lugar no 1º turno, em
        # log-odds. É a régua contra a qual a regressão do swing é medida.
        self.nivel_nacional = sum(m.base_logit * m.validos_base
                                  for m in self.municipios) / peso
        self.nivel_uf = {}
        for uf, muns in self.por_uf.items():
            p = sum(m.validos_base for m in muns) or 1.0
            self.nivel_uf[uf] = sum(m.base_logit * m.validos_base
                                    for m in muns) / p

    # ------------------------------------------------------------------
    def swing_das_pesquisas(self, pct_pl_pesquisas: float) -> float:
        """
        Converte "as pesquisas dão X% para o candidato do PL nos válidos" no
        swing correspondente, em log-odds, contra a base do 1º turno.
        """
        base_pl = sum(_share(m.base_logit) * m.validos_base
                      for m in self.municipios)
        base_pt = self.validos_base_total - base_pl
        alvo = min(max(pct_pl_pesquisas, 1.0), 99.0) / 100.0
        return math.log(alvo / (1 - alvo)) - _logit(base_pl, base_pt)

    # ------------------------------------------------------------------
    def projetar(self, andamento: dict, observado: dict,
                 n_bootstrap: int = 400, semente: int = 12345,
                 prior_swing: float | None = None) -> dict:
        """
        andamento: {"uf/cd": fracao_do_eleitorado_totalizada}
        observado: {"uf": {"pl": votos, "pt": votos}}  — apurado do 2º turno
        prior_swing: swing sugerido pelas pesquisas (use swing_das_pesquisas).
                     Pesa muito no início e desaparece conforme a apuração
                     avança. Sem ele, o modelo parte de "nada mudou".
        """
        for m in self.municipios:
            m.fracao = min(max(andamento.get(m.chave, 0.0), 0.0), 1.0)

        # --- passo 1 e 2: esperado composicional e swing bruto por UF ----
        swing_uf = {}
        peso_uf = {}
        detalhe_uf = {}
        escala_uf = {}
        peso_escala = {}

        for uf, muns in self.por_uf.items():
            obs = observado.get(uf) or {}
            obs_pl = float(obs.get("pl", 0))
            obs_pt = float(obs.get("pt", 0))

            esp_pl = 0.0
            esp_pt = 0.0
            for m in muns:
                if m.fracao <= 0:
                    continue
                s = _share(m.base_logit)          # participação do PL na base
                v = m.fracao * m.validos_base
                esp_pl += v * s
                esp_pt += v * (1.0 - s)

            # Quanto voto válido o 2º turno está rendendo, comparado ao que o
            # 1º turno rendeu nos mesmos lugares.
            #
            # Isto importa porque o modelo estima o que falta como "o mesmo
            # volume de votos do 1º turno". Se brancos, nulos e abstenções
            # mudarem — e eles mudam, geralmente crescendo mais onde o
            # candidato eliminado era forte —, o peso de cada município na
            # soma nacional sai errado. A razão abaixo corrige essa escala
            # com o que de fato saiu das urnas.
            esperado_votos = esp_pl + esp_pt
            votos_obs = obs_pl + obs_pt
            if esperado_votos > 0 and votos_obs >= MIN_VOTOS_SWING:
                escala_uf[uf] = votos_obs / esperado_votos
                peso_escala[uf] = votos_obs

            if votos_obs >= MIN_VOTOS_SWING and esp_pl > 0 and esp_pt > 0:
                sw = _logit(obs_pl, obs_pt) - _logit(esp_pl, esp_pt)
                swing_uf[uf] = sw
                peso_uf[uf] = votos_obs
            detalhe_uf[uf] = {
                "observado_pl": obs_pl, "observado_pt": obs_pt,
                "esperado_pl": esp_pl, "esperado_pt": esp_pt,
            }

        # --- passo 3: encolhimento nacional -> região -> UF --------------
        peso_total = sum(peso_uf.values())
        if peso_total > 0:
            swing_nacional = sum(swing_uf[u] * peso_uf[u] for u in swing_uf) / peso_total
        else:
            swing_nacional = 0.0

        # A âncora das pesquisas entra aqui, e só aqui: ela move o swing
        # nacional enquanto há pouco voto contado, e é engolida pelo dado real
        # depois. Nada do que vem das pesquisas sobrevive a uma apuração
        # adiantada.
        swing_nacional_sem_prior = swing_nacional
        if prior_swing is not None:
            swing_nacional = _encolher(swing_nacional, peso_total,
                                       prior_swing, K_PRIOR)

        por_regiao = {}
        for uf, sw in swing_uf.items():
            r = tse.REGIAO.get(uf, "outros")
            acc = por_regiao.setdefault(r, [0.0, 0.0])
            acc[0] += sw * peso_uf[uf]
            acc[1] += peso_uf[uf]

        swing_regiao = {}
        for r, (soma, peso) in por_regiao.items():
            bruto = soma / peso if peso > 0 else swing_nacional
            swing_regiao[r] = _encolher(bruto, peso, swing_nacional, K_REGIAO)

        # Quanto o swing varia com o nível do lugar, estimado a partir dos
        # estados que já apuraram. É isso que permite inferir um estado ainda
        # não apurado em vez de copiar nele o swing de outro muito diferente.
        b_nivel = (self._coef_nivel(swing_uf, peso_uf, swing_nacional)
                   if USAR_REGRESSAO_NIVEL else 0.0)

        # A escala de votos válidos segue o mesmo encolhimento do swing: com
        # pouca apuração num estado, vale a escala nacional.
        peso_esc_total = sum(peso_escala.values())
        escala_nacional = (sum(escala_uf[u] * peso_escala[u] for u in escala_uf)
                           / peso_esc_total) if peso_esc_total > 0 else 1.0
        escala_final = {}
        for uf in self.por_uf:
            if uf in escala_uf:
                e = _encolher(escala_uf[uf], peso_escala[uf],
                              escala_nacional, K_UF)
            else:
                e = escala_nacional
            # Uma escala fora desta faixa é sinal de dado estranho, não de
            # mudança real de comparecimento.
            escala_final[uf] = min(max(e, 0.75), 1.25)

        swing_final = {}
        for uf in self.por_uf:
            r = tse.REGIAO.get(uf, "outros")
            prior = swing_regiao.get(r, swing_nacional)
            # O prior é corrigido para o nível DESTE estado: um estado onde o
            # candidato era fraco não deve herdar inteiro o swing de uma
            # região onde ele era forte.
            if b_nivel:
                ajuste = b_nivel * (self.nivel_uf[uf] - self.nivel_nacional)
                prior += max(-LIMITE_AJUSTE_NIVEL,
                             min(LIMITE_AJUSTE_NIVEL, ajuste))
            if uf in swing_uf:
                swing_final[uf] = _encolher(swing_uf[uf], peso_uf[uf], prior, K_UF)
            else:
                swing_final[uf] = prior

        # Quanto o swing varia com o perfil do município, estimado a partir da
        # variação entre estados. Serve para corrigir o fato de que, dentro de
        # um mesmo estado, os municípios que apuram primeiro não têm o mesmo
        # perfil dos que apuram por último.
        b_perfil = self._coef_perfil(swing_uf, peso_uf) if USAR_REGRESSAO_PERFIL else 0.0

        # --- passo 4: projeção -------------------------------------------
        projecao = self._somar(swing_final, observado, b_perfil=b_perfil,
                               escala=escala_final)

        # margem por bootstrap
        faixa = self._bootstrap(swing_final, observado, projecao,
                                n_bootstrap, semente, b_perfil, escala_final)

        apurado_votos = sum(d["observado_pl"] + d["observado_pt"]
                            for d in detalhe_uf.values())
        eleitorado_apurado = sum(m.fracao * m.eleitorado for m in self.municipios)
        pct_apurado = (100.0 * eleitorado_apurado / self.eleitorado_total
                       if self.eleitorado_total else 0.0)

        estados = []
        for uf in sorted(self.por_uf):
            d = detalhe_uf[uf]
            o = d["observado_pl"] + d["observado_pt"]
            elei = sum(m.eleitorado for m in self.por_uf[uf])
            apu = sum(m.fracao * m.eleitorado for m in self.por_uf[uf])
            estados.append({
                "uf": uf.upper(),
                "regiao": tse.REGIAO.get(uf, "outros"),
                "pct_apurado": 100.0 * apu / elei if elei else 0.0,
                "obs_pl": 100.0 * d["observado_pl"] / o if o else None,
                "swing": swing_final[uf],
                "swing_bruto": swing_uf.get(uf),
                "proj_pl": projecao["por_uf"][uf]["pct_pl"],
            })

        return {
            "pct_apurado": pct_apurado,
            "votos_apurados": int(apurado_votos),
            "bruto_pl": (100.0 * sum(d["observado_pl"] for d in detalhe_uf.values())
                         / apurado_votos) if apurado_votos else None,
            "projecao_pl": projecao["pct_pl"],
            "projecao_pt": 100.0 - projecao["pct_pl"],
            "faixa_pl": faixa["faixa"],
            "prob_pl": faixa["prob_pl"],
            "swing_nacional": swing_nacional,
            "swing_regiao": swing_regiao,
            "estados": estados,
        }

    # ------------------------------------------------------------------
    def _coef_nivel(self, swing_uf: dict, peso_uf: dict,
                    swing_nacional: float) -> float:
        """
        Inclinação da reta swing × nível, estimada entre os estados apurados.

        Positiva significa "onde o candidato era forte, ele cresceu mais";
        negativa, "onde era forte, caiu mais" — o caso de 2018. Perto de zero
        significa que o país se moveu junto, e aí a correção some sozinha,
        que foi o caso de 2022.

        A regularização (LAMBDA_NIVEL) é deliberadamente pesada: com poucos
        estados apurados, uma reta ajustada sem freio persegue ruído. Ela só
        deixa o coeficiente crescer quando o padrão aparece com volume.
        """
        if len(swing_uf) < 5:
            return 0.0
        pontos = []
        for uf, sw in swing_uf.items():
            nivel = self.nivel_uf.get(uf)
            if nivel is None:
                continue
            pontos.append((nivel, sw, peso_uf[uf]))
        if len(pontos) < 5:
            return 0.0

        # Exige alguma variedade de níveis entre os estados apurados: se só
        # apurou o Sul, não há como enxergar a inclinação.
        niveis = [p[0] for p in pontos]
        if max(niveis) - min(niveis) < 0.35:
            return 0.0

        peso_total = sum(p[2] for p in pontos)
        if peso_total <= 0:
            return 0.0
        x_medio = sum(p[0] * p[2] for p in pontos) / peso_total
        y_medio = sum(p[1] * p[2] for p in pontos) / peso_total
        num = sum(p[2] * (p[0] - x_medio) * (p[1] - y_medio) for p in pontos)
        den = sum(p[2] * (p[0] - x_medio) ** 2 for p in pontos)
        return num / (den + LAMBDA_NIVEL * peso_total)

    # ------------------------------------------------------------------
    def _coef_perfil(self, swing_uf: dict, peso_uf: dict) -> float:
        """
        Regressão ponderada e regularizada do swing estadual sobre o perfil
        do estado. Com 27 pontos, a regularização é o que impede o
        coeficiente de perseguir ruído.
        """
        if len(swing_uf) < 6:
            return 0.0
        pontos = []
        for uf, sw in swing_uf.items():
            muns = self.por_uf.get(uf) or []
            base = sum(m.validos_base for m in muns)
            if base <= 0:
                continue
            perfil = sum(m.perfil * m.validos_base for m in muns) / base
            pontos.append((perfil, sw, peso_uf[uf]))
        if len(pontos) < 6:
            return 0.0

        peso_total = sum(p[2] for p in pontos)
        if peso_total <= 0:
            return 0.0
        x_medio = sum(p[0] * p[2] for p in pontos) / peso_total
        y_medio = sum(p[1] * p[2] for p in pontos) / peso_total
        num = sum(p[2] * (p[0] - x_medio) * (p[1] - y_medio) for p in pontos)
        den = sum(p[2] * (p[0] - x_medio) ** 2 for p in pontos)
        return num / (den + LAMBDA_PERFIL * peso_total)

    # ------------------------------------------------------------------
    def _somar(self, swing_final: dict, observado: dict,
               ruido: dict | None = None, b_perfil: float = 0.0,
               escala: dict | None = None) -> dict:
        """Observado (real) + restante (modelado), município a município."""
        total_pl = 0.0
        total_pt = 0.0
        por_uf = {}

        for uf, muns in self.por_uf.items():
            obs = observado.get(uf) or {}
            pl = float(obs.get("pl", 0))
            pt = float(obs.get("pt", 0))

            sw = swing_final.get(uf, 0.0)
            if ruido:
                sw += ruido.get(uf, 0.0)

            # Perfil médio do que já apurou neste estado: o swing medido vale
            # para esse perfil, e os municípios que faltam são comparados a ele.
            peso_apurado = sum(m.fracao * m.validos_base for m in muns)
            if b_perfil and peso_apurado > 0:
                perfil_apurado = sum(m.perfil * m.fracao * m.validos_base
                                     for m in muns) / peso_apurado
            else:
                perfil_apurado = None

            fator = (escala or {}).get(uf, 1.0)
            for m in muns:
                falta = 1.0 - m.fracao
                if falta <= 1e-9:
                    continue
                sw_m = sw
                if perfil_apurado is not None:
                    sw_m += b_perfil * (m.perfil - perfil_apurado)
                s = _share(m.base_logit + sw_m)
                # O volume do que falta é corrigido pelo que o 2º turno está
                # de fato rendendo naquele estado.
                v = falta * m.validos_base * fator
                pl += v * s
                pt += v * (1.0 - s)

            soma = pl + pt
            por_uf[uf] = {"pl": pl, "pt": pt,
                          "pct_pl": 100.0 * pl / soma if soma else 50.0}
            total_pl += pl
            total_pt += pt

        soma = total_pl + total_pt
        return {"pl": total_pl, "pt": total_pt,
                "pct_pl": 100.0 * total_pl / soma if soma else 50.0,
                "por_uf": por_uf}

    # ------------------------------------------------------------------
    def _bootstrap(self, swing_final: dict, observado: dict, central: dict,
                   n: int, semente: int, b_perfil: float = 0.0,
                   escala: dict | None = None) -> dict:
        """
        Incerteza: o swing de cada UF é perturbado por um termo comum
        (erro nacional, que não some com mais apuração) e um termo próprio,
        ambos encolhendo conforme a apuração avança.
        """
        if n <= 0:
            return {"faixa": [central["pct_pl"], central["pct_pl"]],
                    "prob_pl": 1.0 if central["pct_pl"] > 50 else 0.0}

        rng = random.Random(semente)
        falta_total = sum((1.0 - m.fracao) * m.validos_base
                          for m in self.municipios)
        frac_falta = (falta_total / self.validos_base_total
                      if self.validos_base_total else 1.0)
        # Quanto menos falta apurar, menos espaço há para errar.
        #
        # ATENÇÃO ao nome: esta variável é o DESVIO do ruído, e não tem nada
        # a ver com o parâmetro `escala` (o fator de votos válidos por UF).
        # Chamar as duas de "escala" fazia a local sobrescrever o parâmetro,
        # e daí o bootstrap rodava sem a correção de votos válidos — e
        # estourava AttributeError ao passar um float onde se esperava dict.
        # O erro só aparecia com n_bootstrap > 0, que os backtests não usam.
        sigma = SIGMA_SWING * math.sqrt(max(frac_falta, 0.0))

        amostras = []
        ufs = list(self.por_uf)
        for _ in range(n):
            comum = rng.gauss(0.0, sigma * 0.75)
            ruido = {u: comum + rng.gauss(0.0, sigma * 0.6) for u in ufs}
            amostras.append(
                self._somar(swing_final, observado, ruido, b_perfil, escala)["pct_pl"])

        amostras.sort()
        lo = amostras[int(0.05 * (n - 1))]
        hi = amostras[int(0.95 * (n - 1))]
        prob = sum(1 for a in amostras if a > 50.0) / float(n)
        return {"faixa": [lo, hi], "prob_pl": prob}
