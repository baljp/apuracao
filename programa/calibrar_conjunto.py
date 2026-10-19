"""
Calibra os parâmetros olhando para 2018 E 2022 ao mesmo tempo.

Calibrar só em 2022 é perigoso: aquela eleição teve um swing quase uniforme
pelo país (amplitude de 0,6 ponto entre regiões), então qualquer parâmetro
funciona bem. 2018 foi o oposto — o swing variou de −2,2 pontos no Norte a
−8,1 no Sudeste. Um parâmetro só é confiável se aguentar os dois casos.

O critério é o erro máximo entre os dois anos (o pior caso), não a média: um
modelo que vai muito bem num ano e mal no outro não serve para prever um ano
que ainda não aconteceu.

Uso:  python3 calibrar_conjunto.py
"""

from __future__ import annotations

import os
import sys

import backtest
import modelo

ANOS = (2018, 2022)


def erro_do_ano(ano: int, desde: float = 5.0) -> tuple:
    base, sequencia = backtest.carregar(ano)
    linhas, alvo = backtest.rodar(
        base, sequencia, passos=[p / 100.0 for p in range(1, 100, 3)])
    erros = [abs(l["erro_proj"]) for l in linhas if l["pct"] >= desde]
    if not erros:
        return 99.0, 99.0
    return sum(erros) / len(erros), max(erros)


def main() -> int:
    for ano in ANOS:
        if not os.path.exists(backtest.caminho_base(ano)):
            print("Falta base%d.json — rode: python3 preparar_historico.py --ano %d"
                  % (ano, ano))
            return 1

    print("Varrendo parâmetros contra 2018 e 2022.\n")
    print("  %-9s %-9s  %-16s %-16s %s"
          % ("K_UF", "K_REGIAO", "2018 méd/máx", "2022 méd/máx", "pior caso"))
    print("  " + "-" * 70)

    melhor = None
    for k_uf in (20_000, 45_000, 90_000, 180_000, 400_000):
        for k_reg in (10_000, 25_000, 50_000, 120_000):
            modelo.K_UF = float(k_uf)
            modelo.K_REGIAO = float(k_reg)
            r = {ano: erro_do_ano(ano) for ano in ANOS}
            pior = max(r[ano][1] for ano in ANOS)
            marca = ""
            if melhor is None or pior < melhor[0]:
                melhor = (pior, k_uf, k_reg, dict(r))
                marca = "  <--"
            print("  %-9d %-9d  %5.2f / %5.2f    %5.2f / %5.2f     %5.2f%s"
                  % (k_uf, k_reg, r[2018][0], r[2018][1],
                     r[2022][0], r[2022][1], pior, marca))

    pior, k_uf, k_reg, r = melhor
    print("\nMelhor pelo pior caso: K_UF=%d  K_REGIAO=%d" % (k_uf, k_reg))
    print("  2018: erro médio %.2f pp, máximo %.2f pp" % r[2018])
    print("  2022: erro médio %.2f pp, máximo %.2f pp" % r[2022])
    print("\nValores atualmente no modelo: K_UF=%d  K_REGIAO=%d"
          % (180_000, 90_000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
