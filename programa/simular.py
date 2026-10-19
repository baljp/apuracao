"""
50 eleições cegas: testa o modelo contra resultados que ele nunca viu.

Por que isto existe. Duas eleições reais (2018 e 2022) são pouca coisa para
saber onde um modelo quebra. Aqui o eleitorado é o real — os 5.716 municípios
com seu eleitorado e seu voto no 1º turno de 2026 — mas o resultado do 2º
turno é inventado, e inventado de propósito com as estruturas que o modelo NÃO
pressupõe:

  swing desigual entre regiões   o modelo supõe suavidade geográfica
  swing que depende do nível     onde o candidato era forte, cai mais
  choques estaduais              um estado foge do padrão da sua região
  ruído município a município    nem vizinhos se movem igual

Um gerador que produzisse exatamente o que o modelo espera daria notas altas
sem significar nada. A faixa de cada parâmetro é ancorada nas duas eleições
reais: 2022 fica perto do lado fácil (regiões quase idênticas) e 2018 perto do
difícil (amplitude de 5,9 pontos entre regiões).

A ordem de chegada é a real, observada no 1º turno de 2026.

Uso:
    python3 simular.py                 50 cenários
    python3 simular.py --n 200         mais cenários
    python3 simular.py --semente 7     outra rodada
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

import modelo
import tse

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(AQUI, "base_1t.json")
ORDEM = os.path.join(AQUI, "ordem_1t_2026.json")

MARCOS = [0.5, 1, 2, 3, 5, 10, 20, 50]
REGIOES = ["norte", "nordeste", "centro-oeste", "sudeste", "sul", "exterior"]


def carregar():
    with open(BASE, encoding="utf-8") as fh:
        base = json.load(fh)
    with open(ORDEM, encoding="utf-8") as fh:
        ordem = json.load(fh)["ordem"]
    return base, ordem


def sortear_cenario(rng: random.Random) -> dict:
    """
    Um mundo possível. Em log-odds, que é a escala em que o modelo trabalha.

    Referências reais: 2018 teve swing nacional de -0,21 e regiões espalhadas
    por 0,30 em log-odds; 2022 teve +0,08 e regiões praticamente coladas.
    """
    return {
        "nacional": rng.gauss(0.0, 0.16),
        # Quão desigual é o país neste cenário. Vai do colado (2022) ao
        # muito espalhado (pior que 2018).
        "sigma_regiao": rng.uniform(0.0, 0.18),
        # Dependência do nível: negativo = onde era forte, caiu mais.
        "coef_nivel": rng.uniform(-0.18, 0.08),
        "sigma_uf": rng.uniform(0.01, 0.07),
        "sigma_municipio": rng.uniform(0.02, 0.09),
        # Choque em um estado sorteado, que foge do padrão da sua região.
        "choque_uf": rng.choice([None] + [u for u in tse.UFS if u != "zz"]),
        "choque": rng.gauss(0.0, 0.12),
    }


def gerar_alvo(mdl, cen: dict, rng: random.Random):
    """Aplica o cenário à base e devolve o resultado 'real' deste mundo."""
    por_regiao = {r: rng.gauss(0.0, cen["sigma_regiao"]) for r in REGIOES}
    por_uf = {u: rng.gauss(0.0, cen["sigma_uf"]) for u in mdl.por_uf}

    alvo = {}
    total_pl = total_pt = 0.0
    for m in mdl.municipios:
        sw = (cen["nacional"]
              + por_regiao.get(m.regiao, 0.0)
              + por_uf.get(m.uf, 0.0)
              + cen["coef_nivel"] * (m.base_logit - mdl.nivel_nacional)
              + rng.gauss(0.0, cen["sigma_municipio"]))
        if cen["choque_uf"] and m.uf == cen["choque_uf"]:
            sw += cen["choque"]
        s = modelo._share(m.base_logit + sw)
        # O comparecimento do 2º turno não é idêntico ao do 1º; uma variação
        # pequena e aleatória evita que o modelo acerte por construção.
        v = m.validos_base * rng.uniform(0.96, 1.02)
        pl, pt = v * s, v * (1 - s)
        alvo[m.chave] = (pl, pt)
        total_pl += pl
        total_pt += pt
    return alvo, 100.0 * total_pl / (total_pl + total_pt)


def rodar_cenario(mdl, ordem, cen, rng):
    alvo, verdade = gerar_alvo(mdl, cen, rng)

    sequencia = [o for o in ordem if o["chave"] in mdl.por_chave]
    eleitorado = sum(mdl.por_chave[o["chave"]].eleitorado for o in sequencia)

    andamento, observado = {}, {}
    acc = 0.0
    i = 0
    erros = {}

    for marco in MARCOS:
        limite = (marco / 100.0) * eleitorado
        while i < len(sequencia) and acc < limite:
            chave = sequencia[i]["chave"]
            m = mdl.por_chave[chave]
            andamento[chave] = 1.0
            uf = observado.setdefault(m.uf, {"pl": 0.0, "pt": 0.0})
            pl, pt = alvo[chave]
            uf["pl"] += pl
            uf["pt"] += pt
            acc += m.eleitorado
            i += 1
        if not observado:
            continue
        r = mdl.projetar(andamento, observado, n_bootstrap=0)
        bruto_pl = sum(o["pl"] for o in observado.values())
        bruto_tot = bruto_pl + sum(o["pt"] for o in observado.values())
        erros[marco] = {
            "proj": r["projecao_pl"] - verdade,
            "bruto": (100.0 * bruto_pl / bruto_tot) - verdade,
        }
    return erros, verdade, cen


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--semente", type=int, default=20261025)
    args = p.parse_args()

    if not os.path.exists(BASE) or not os.path.exists(ORDEM):
        print("Faltam base_1t.json / ordem_1t_2026.json")
        return 1

    base, ordem = carregar()
    mdl = modelo.Modelo(base)
    rng = random.Random(args.semente)

    print("%d eleições cegas sobre os %d municípios reais."
          % (args.n, len(mdl.municipios)))
    print("Ordem de chegada: a real do 1º turno de 2026.\n")

    todos = []
    for k in range(args.n):
        cen = sortear_cenario(rng)
        erros, verdade, cen = rodar_cenario(mdl, ordem, cen, rng)
        todos.append((erros, verdade, cen))
        if (k + 1) % 10 == 0:
            print("  %d/%d cenários" % (k + 1, args.n), flush=True)

    print("\n  %-9s %-26s %s" % ("apurado", "projeção do modelo", "percentual bruto"))
    print("  %-9s %-26s %s" % ("", "médio / p90 / pior", "médio / pior"))
    print("  " + "-" * 62)
    for marco in MARCOS:
        ep = sorted(abs(t[0][marco]["proj"]) for t in todos if marco in t[0])
        eb = sorted(abs(t[0][marco]["bruto"]) for t in todos if marco in t[0])
        if not ep:
            continue
        p90 = ep[int(0.9 * (len(ep) - 1))]
        print("  %6.1f%%   %5.2f / %5.2f / %5.2f pp      %5.2f / %5.2f pp"
              % (marco, sum(ep) / len(ep), p90, ep[-1],
                 sum(eb) / len(eb), eb[-1]))

    # Onde o modelo sofre: relação entre desigualdade do cenário e erro.
    print("\n  Erro aos 5% conforme o país se move de forma mais desigual:")
    faixas = [(0.0, 0.04), (0.04, 0.08), (0.08, 0.12), (0.12, 0.18)]
    for lo, hi in faixas:
        sel = [abs(t[0][5]["proj"]) for t in todos
               if 5 in t[0] and lo <= t[2]["sigma_regiao"] < hi]
        if not sel:
            continue
        rotulo = "σ regiões %.2f–%.2f" % (lo, hi)
        ref = ("  (2022 fica aqui)" if hi <= 0.04 else
               "  (2018 fica aqui)" if lo >= 0.08 and lo < 0.12 else "")
        print("    %-20s n=%2d   erro médio %.2f pp, pior %.2f pp%s"
              % (rotulo, len(sel), sum(sel) / len(sel), max(sel), ref))

    acertou = sum(1 for t in todos if 5 in t[0]
                  and (t[1] > 50) == (t[1] + t[0][5]["proj"] > 50))
    n5 = sum(1 for t in todos if 5 in t[0])
    print("\n  Vencedor apontado corretamente com 5%% apurado: %d de %d"
          % (acertou, n5))
    acertou_bruto = sum(1 for t in todos if 5 in t[0]
                        and (t[1] > 50) == (t[1] + t[0][5]["bruto"] > 50))
    print("  (o percentual bruto acertaria %d de %d)" % (acertou_bruto, n5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
