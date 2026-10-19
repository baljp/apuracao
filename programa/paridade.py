"""
Exporta cenários de apuração PARCIAL para comparar Python e JavaScript.

Por que isto existe. O conferir.mjs comparava os dois modelos apenas com
100% apurado — ponto em que não sobra nada para projetar e qualquer modelo
acerta, porque a resposta já está nos votos. Um teste que só pergunta o que
não precisa de modelo não testa modelo nenhum.

Foi essa cegueira que deixou passar uma divergência real: o Python corrigia
o volume do que falta pelo rendimento de voto válido do 2º turno (a correção
de brancos e nulos) e o JavaScript não. Os dois concordavam em 100% e
divergiam exatamente onde a página é usada — no meio da noite.

Aqui o cenário é congelado em vários pontos da apuração, com os mesmos dados
de entrada para os dois lados, e a comparação é feita onde o modelo de fato
trabalha.

Uso:
    python3 paridade.py            gera cenarios_paridade.json
    node ../paridade.mjs           roda o lado JS e compara
"""

from __future__ import annotations

import json
import os
import sys

import modelo
import tse

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

MARCOS = [0.5, 1, 2, 3, 5, 10, 20, 35, 50, 75, 95]

# Swing inventado por região, em log-odds, da ordem do que se viu em 2018.
SWING_REGIAO = {"sudeste": 0.08, "sul": 0.14, "centro-oeste": 0.11,
                "nordeste": -0.17, "norte": 0.03, "outros": 0.0}

# Rendimento de voto válido por região: é o que a correção de brancos, nulos
# e abstenção existe para capturar.
RENDIMENTO_REGIAO = {"sudeste": 0.97, "sul": 1.03, "centro-oeste": 1.01,
                     "nordeste": 0.91, "norte": 0.94, "outros": 1.0}


def main() -> int:
    with open(os.path.join(RAIZ, "base.json"), encoding="utf-8") as fh:
        base_site = json.load(fh)
    with open(os.path.join(AQUI, "ordem_1t_2026.json"), encoding="utf-8") as fh:
        ordem = [o["chave"] for o in json.load(fh)["ordem"]]

    # A base do site é colunar e a do Python é por município. Para a
    # comparação valer, os dois têm de ler EXATAMENTE os mesmos números:
    # a base do site é convertida aqui, em vez de carregar o arquivo que o
    # Python usa normalmente.
    mdl = modelo.Modelo({"municipios": [
        {"uf": base_site["ufs"][i], "cd": base_site["cds"][i],
         "nm": base_site["nms"][i], "eleitorado": base_site["ele"][i],
         "votos": {tse.NUM_PL: base_site["pl"][i],
                   tse.NUM_PT: base_site["pt"][i],
                   "99": base_site["out"][i]}}
        for i in range(len(base_site["ufs"]))]})
    idx = {base_site["ufs"][i] + "/" + base_site["cds"][i]: i
           for i in range(len(base_site["ufs"]))}
    total = sum(base_site["ele"])

    cenarios = []
    andamento, observado = {}, {}
    acc = 0.0
    pos = 0

    for marco in MARCOS:
        limite = marco / 100.0 * total
        while pos < len(ordem) and acc < limite:
            chave = ordem[pos]
            pos += 1
            i = idx.get(chave)
            if i is None:
                continue
            andamento[chave] = 1.0
            sigla = base_site["ufs"][i]

            # Usar os votos do 1º turno como "observado" daria swing zero e
            # rendimento de voto válido exatamente igual ao da base — ou
            # seja, a correção de votos válidos ficaria multiplicando por 1 e
            # o teste não exercitaria justamente a parte que divergia entre
            # Python e JavaScript.
            #
            # Então o 2º turno é inventado com as duas coisas que precisam
            # ser testadas: swing que varia por região, e comparecimento que
            # varia por região (o Nordeste rendendo menos voto válido que o
            # Sul, por exemplo). Os números não precisam ser realistas; o que
            # importa é que os dois modelos recebam o mesmo e concordem.
            reg = tse.REGIAO.get(sigla, "outros")
            sw = SWING_REGIAO.get(reg, 0.0)
            rend = RENDIMENTO_REGIAO.get(reg, 1.0)

            pl0 = base_site["pl"][i]
            pt0 = base_site["pt"][i]
            tot = (pl0 + pt0) * rend
            if pl0 + pt0 > 0:
                import math as _m
                lg = _m.log(max(pl0, 1e-9) / max(pt0, 1e-9)) + sw
                s_pl = 1.0 / (1.0 + _m.exp(-lg))
            else:
                s_pl = 0.5

            uf = observado.setdefault(sigla, {"pl": 0.0, "pt": 0.0})
            uf["pl"] += tot * s_pl
            uf["pt"] += tot * (1.0 - s_pl)
            acc += base_site["ele"][i]

        r = mdl.projetar(dict(andamento), {k: dict(v) for k, v in observado.items()},
                         n_bootstrap=240, semente=12345)
        cenarios.append({
            "marco": marco,
            "andamento": dict(andamento),
            "observado": {k: dict(v) for k, v in observado.items()},
            "python": {
                "projecao_pl": r["projecao_pl"],
                "pct_apurado": r["pct_apurado"],
                "faixa_pl": r["faixa_pl"],
                "prob_pl": r["prob_pl"],
                "estados": {e["uf"]: e["proj_pl"] for e in r["estados"]},
            },
        })
        print("  %5.1f%% apurado -> projeção %.6f" % (marco, r["projecao_pl"]))

    destino = os.path.join(AQUI, "cenarios_paridade.json")
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(cenarios, fh)
    print("\n  %d cenários em %s" % (len(cenarios), destino))
    print("  agora rode:  node paridade.mjs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
