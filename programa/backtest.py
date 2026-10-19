"""
Backtest: reproduz a apuração do 2º turno de 2022 e mede o erro do modelo
a cada 1% apurado.

É o único jeito honesto de saber se o modelo funciona. A regra do jogo:

  base  = 1º turno de 2022 (o que o modelo tem direito de saber)
  alvo  = 2º turno de 2022 (Bolsonaro 49,10% x Lula 50,90%) — o modelo NUNCA vê
  ordem = a ordem real de chegada observada no 1º turno de 2026

A ordem de chegada vem de 2026 de propósito: é a ordem real mais recente que
existe (os arquivos de andamento do TSE registram o horário em que cada
município concluiu), e a logística de apuração é a mesma — as mesmas zonas
eleitorais, nos mesmos municípios, com o mesmo ritmo. Usar uma ordem inventada
tornaria o teste inútil.

Municípios entram inteiros, na ordem em que fecharam. A cada 1% do eleitorado
totalizado, o modelo projeta e o erro é registrado.

Uso:
  python3 backtest.py              roda o backtest com os parâmetros atuais
  python3 backtest.py --calibrar   procura os parâmetros que minimizam o erro
"""

from __future__ import annotations

import json
import os
import sys

import modelo
import tse

AQUI = os.path.dirname(os.path.abspath(__file__))
ORDEM = os.path.join(AQUI, "ordem_1t_2026.json")

NOMES = {
    2006: ("Alckmin", "Lula"),
    2010: ("Serra", "Dilma"),
    2014: ("Aécio", "Dilma"),
    2018: ("Bolsonaro", "Haddad"),
    2022: ("Bolsonaro", "Lula"),
}


def caminho_base(ano: int) -> str:
    return os.path.join(AQUI, "base%d.json" % ano)


def carregar(ano: int = 2022):
    with open(caminho_base(ano), encoding="utf-8") as fh:
        base = json.load(fh)
    with open(ORDEM, encoding="utf-8") as fh:
        ordem = json.load(fh)["ordem"]

    por_chave = {"%s/%s" % (m["uf"], m["cd"]): m for m in base["municipios"]}

    # Municípios na ordem real de chegada; os que não casam (criados ou
    # extintos entre as eleições, exterior) vão para o fim.
    sequencia = []
    vistos = set()
    for item in ordem:
        m = por_chave.get(item["chave"])
        if m is not None:
            sequencia.append(m)
            vistos.add(item["chave"])
    for chave, m in por_chave.items():
        if chave not in vistos:
            sequencia.append(m)
    return base, sequencia


def resultado_final(base) -> float:
    pl = sum(m["alvo"]["pl"] for m in base["municipios"])
    pt = sum(m["alvo"]["pt"] for m in base["municipios"])
    return 100.0 * pl / (pl + pt)


def rodar(base, sequencia, passos=None, n_bootstrap=0, verbose=False):
    """Devolve [(pct_apurado, pct_bruto, pct_projetado, faixa), ...]."""
    mdl = modelo.Modelo(base)
    alvo = resultado_final(base)

    eleitorado_total = sum(m["eleitorado"] for m in sequencia)
    passos = passos or [p / 100.0 for p in range(1, 100)]

    andamento = {}
    observado = {}
    acumulado = 0.0
    obs_pl = obs_pt = 0.0
    i = 0
    linhas = []

    for alvo_frac in passos:
        limite = alvo_frac * eleitorado_total
        while i < len(sequencia) and acumulado < limite:
            m = sequencia[i]
            chave = "%s/%s" % (m["uf"], m["cd"])
            andamento[chave] = 1.0
            uf = observado.setdefault(m["uf"], {"pl": 0.0, "pt": 0.0})
            uf["pl"] += m["alvo"]["pl"]
            uf["pt"] += m["alvo"]["pt"]
            obs_pl += m["alvo"]["pl"]
            obs_pt += m["alvo"]["pt"]
            acumulado += m["eleitorado"]
            i += 1

        if obs_pl + obs_pt == 0:
            continue
        r = mdl.projetar(andamento, observado, n_bootstrap=n_bootstrap)
        bruto = 100.0 * obs_pl / (obs_pl + obs_pt)
        linhas.append({
            "pct": r["pct_apurado"],
            "bruto": bruto,
            "proj": r["projecao_pl"],
            "faixa": r["faixa_pl"],
            "erro_bruto": bruto - alvo,
            "erro_proj": r["projecao_pl"] - alvo,
        })
        if verbose:
            print("  %5.1f%%  bruto %6.2f (%+6.2f)   projeção %6.2f (%+5.2f)"
                  % (r["pct_apurado"], bruto, bruto - alvo,
                     r["projecao_pl"], r["projecao_pl"] - alvo))
    return linhas, alvo


def resumo(linhas, alvo, ano=2022):
    marcos = [1, 2, 3, 5, 10, 15, 20, 30, 50, 75]
    print("\n  %-7s %-22s %-22s" % ("apurado", "percentual bruto", "projeção do modelo"))
    print("  " + "-" * 54)
    for marco in marcos:
        cand = [l for l in linhas if l["pct"] >= marco]
        if not cand:
            continue
        l = cand[0]
        print("  %5.0f%%  %6.2f%%  (erro %+6.2f)   %6.2f%%  (erro %+5.2f)"
              % (marco, l["bruto"], l["erro_bruto"], l["proj"], l["erro_proj"]))
    print("  " + "-" * 54)
    print("  resultado real do 2º turno de %d: %.2f%% para %s"
          % (ano, alvo, NOMES.get(ano, ("A", "B"))[0]))

    apos5 = [abs(l["erro_proj"]) for l in linhas if l["pct"] >= 5]
    apos1 = [abs(l["erro_proj"]) for l in linhas if l["pct"] >= 1]
    if apos5:
        print("\n  erro da projeção a partir de 5%% apurado:  médio %.2f pp, "
              "máximo %.2f pp" % (sum(apos5) / len(apos5), max(apos5)))
    if apos1:
        print("  erro da projeção a partir de 1%% apurado:  médio %.2f pp, "
              "máximo %.2f pp" % (sum(apos1) / len(apos1), max(apos1)))


def erro_medio(base, sequencia, desde=2.0) -> float:
    linhas, alvo = rodar(base, sequencia,
                         passos=[p / 100.0 for p in range(1, 100, 2)])
    erros = [abs(l["erro_proj"]) for l in linhas if l["pct"] >= desde]
    return sum(erros) / len(erros) if erros else 99.0


def calibrar(base, sequencia):
    print("Procurando os parâmetros de encolhimento que minimizam o erro.\n")
    melhor = None
    for k_uf in (60_000, 120_000, 180_000, 300_000, 600_000):
        for k_reg in (30_000, 60_000, 120_000, 250_000):
            modelo.K_UF = float(k_uf)
            modelo.K_REGIAO = float(k_reg)
            e = erro_medio(base, sequencia)
            marca = ""
            if melhor is None or e < melhor[0]:
                melhor = (e, k_uf, k_reg)
                marca = "  <-- melhor até aqui"
            print("  K_UF=%7d  K_REGIAO=%7d  erro médio %.3f pp%s"
                  % (k_uf, k_reg, e, marca))
    print("\nMelhor combinação: K_UF=%d  K_REGIAO=%d  (erro médio %.3f pp)"
          % (melhor[1], melhor[2], melhor[0]))
    return melhor


def main() -> int:
    ano = 2022
    for i, arg in enumerate(sys.argv):
        if arg == "--ano" and i + 1 < len(sys.argv):
            ano = int(sys.argv[i + 1])

    if not os.path.exists(caminho_base(ano)):
        print("Falta base%d.json — rode antes: "
              "python3 preparar_historico.py --ano %d" % (ano, ano))
        return 1
    if not os.path.exists(ORDEM):
        print("Falta ordem_1t_2026.json — rode antes: python3 andamento.py")
        return 1

    base, sequencia = carregar(ano)
    a, b = NOMES.get(ano, ("finalista A", "finalista B"))
    print("Backtest do 2º turno de %d  (%s x %s)" % (ano, a, b))
    print("  %d municípios, ordem de chegada real do 1º turno de 2026"
          % len(sequencia))

    # O swing verdadeiro: quanto o resultado do 2º turno se afastou do 1º.
    # Quanto maior, mais difícil o teste.
    pl1 = sum(m["votos"].get("22", 0) for m in base["municipios"])
    pt1 = sum(m["votos"].get("13", 0) for m in base["municipios"])
    base_pct = 100.0 * pl1 / (pl1 + pt1)
    alvo_pct = resultado_final(base)
    print("  1º turno entre os dois finalistas: %.2f%% para %s" % (base_pct, a))
    print("  2º turno (resultado real):         %.2f%% para %s" % (alvo_pct, a))
    print("  swing a ser descoberto pelo modelo: %+.2f pp\n"
          % (alvo_pct - base_pct))

    if "--calibrar" in sys.argv:
        melhor = calibrar(base, sequencia)
        modelo.K_UF, modelo.K_REGIAO = float(melhor[1]), float(melhor[2])

    linhas, alvo = rodar(base, sequencia, n_bootstrap=0)
    resumo(linhas, alvo, ano)
    return 0


if __name__ == "__main__":
    sys.exit(main())
