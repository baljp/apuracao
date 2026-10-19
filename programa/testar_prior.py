"""
Mede se ancorar o swing nas pesquisas finais melhora ou piora a projeção.

O teste é honesto de propósito: usa as pesquisas finais REAIS de cada ano,
inclusive quando elas estavam erradas.

  2018 — as pesquisas acertaram quase na mosca. Ibope e Datafolha na véspera
         davam Bolsonaro com 55% dos válidos; ele fez 55,13%.
  2022 — as pesquisas erraram cerca de 2 pontos. Davam Lula com 52% dos
         válidos (Bolsonaro 48%); o resultado foi 50,90% a 49,10%.

Ou seja: um ano em que a âncora ajuda e um em que ela atrapalha. Se o ganho
em 2018 for maior que a perda em 2022, a âncora vale a pena; se não, não vale.

Uso:  python3 testar_prior.py
"""

from __future__ import annotations

import os
import sys

import backtest
import modelo

# Percentual do finalista do PL (Bolsonaro, nos dois casos) nos votos válidos,
# segundo as pesquisas finais da véspera.
PESQUISAS_FINAIS = {
    2018: 55.0,   # pesquisas diziam 55 — resultado real: 55,13 (erro 0,1)
    2022: 48.0,   # pesquisas diziam 48 — resultado real: 49,10 (erro 1,1)
}


def rodar(ano: int, com_prior: bool):
    base, sequencia = backtest.carregar(ano)
    mdl = modelo.Modelo(base)
    prior = mdl.swing_das_pesquisas(PESQUISAS_FINAIS[ano]) if com_prior else None

    alvo = backtest.resultado_final(base)
    eleitorado = sum(m["eleitorado"] for m in sequencia)
    andamento, observado = {}, {}
    acc = 0.0
    i = 0
    linhas = []

    for marco in [p / 100.0 for p in range(1, 100, 2)]:
        limite = marco * eleitorado
        while i < len(sequencia) and acc < limite:
            m = sequencia[i]
            andamento["%s/%s" % (m["uf"], m["cd"])] = 1.0
            uf = observado.setdefault(m["uf"], {"pl": 0.0, "pt": 0.0})
            uf["pl"] += m["alvo"]["pl"]
            uf["pt"] += m["alvo"]["pt"]
            acc += m["eleitorado"]
            i += 1
        if not observado:
            continue
        r = mdl.projetar(andamento, observado, n_bootstrap=0, prior_swing=prior)
        linhas.append((r["pct_apurado"], r["projecao_pl"] - alvo))
    return linhas


def erro_em(linhas, pct):
    for p, e in linhas:
        if p >= pct:
            return e
    return None


def main() -> int:
    for ano in PESQUISAS_FINAIS:
        if not os.path.exists(backtest.caminho_base(ano)):
            print("Falta base%d.json" % ano)
            return 1

    print("Efeito de ancorar o swing nas pesquisas finais\n")
    marcos = [1, 3, 5, 10, 20, 50]
    resumo = {}

    for ano in sorted(PESQUISAS_FINAIS):
        sem = rodar(ano, False)
        com = rodar(ano, True)
        resumo[ano] = (sem, com)
        a, b = backtest.NOMES[ano]
        print("=== %d (%s x %s) — pesquisas finais davam %.0f%% para %s ==="
              % (ano, a, b, PESQUISAS_FINAIS[ano], a))
        print("  %-9s %-14s %-14s %s" % ("apurado", "sem âncora", "com âncora", "efeito"))
        for mk in marcos:
            e1, e2 = erro_em(sem, mk), erro_em(com, mk)
            if e1 is None or e2 is None:
                continue
            melhora = abs(e1) - abs(e2)
            sinal = "melhora" if melhora > 0.02 else ("piora" if melhora < -0.02 else "igual")
            print("  %5d%%    %+7.2f pp     %+7.2f pp     %s %.2f"
                  % (mk, e1, e2, sinal, abs(melhora)))
        print()

    print("Balanço geral (erro médio absoluto a partir de 2% apurado):")
    total_sem = total_com = 0.0
    for ano, (sem, com) in resumo.items():
        ms = sum(abs(e) for p, e in sem if p >= 2) / max(1, len([1 for p, _ in sem if p >= 2]))
        mc = sum(abs(e) for p, e in com if p >= 2) / max(1, len([1 for p, _ in com if p >= 2]))
        total_sem += ms
        total_com += mc
        print("  %d:  sem %.2f pp   com %.2f pp   (%+.2f)" % (ano, ms, mc, ms - mc))
    print("  ---")
    print("  média dos dois anos: sem %.2f pp   com %.2f pp   (%+.2f)"
          % (total_sem / 2, total_com / 2, (total_sem - total_com) / 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
