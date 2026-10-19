"""
Calibra o modelo contra as eleições simuladas, e confere nas reais.

Calibrar em 2018 e 2022 tem um problema: são dois pontos. Qualquer parâmetro
que vá bem neles pode estar apenas decorando duas eleições. Aqui a calibração
usa dezenas de mundos possíveis, todos com a MESMA semente entre as
combinações, de modo que a comparação é justa — cada ajuste enfrenta
exatamente os mesmos cenários.

O critério é o erro aos 5% apurado: é o momento em que uma projeção ainda tem
valor (a apuração mal começou) e já deveria ser confiável. Olhamos a média e
o pior caso, porque um modelo que vai bem em média e explode num cenário é
pior do que um modelo um pouco mais fraco e estável.

No fim, os melhores parâmetros são conferidos contra 2018 e 2022 de verdade.

Uso:  python3 calibrar_simulado.py [--n 30]
"""

from __future__ import annotations

import argparse
import os
import random
import sys

import backtest
import modelo
import simular


def avaliar(mdl, ordem, cenarios, marco=5):
    erros = []
    for cen, semente in cenarios:
        rng = random.Random(semente)
        res, verdade, _ = simular.rodar_cenario(mdl, ordem, cen, rng)
        if marco in res:
            erros.append(abs(res[marco]["proj"]))
    if not erros:
        return 99.0, 99.0
    return sum(erros) / len(erros), max(erros)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--semente", type=int, default=20261025)
    args = p.parse_args()

    base, ordem = simular.carregar()
    mdl = modelo.Modelo(base)

    # Os cenários são sorteados uma vez e reutilizados em todas as
    # combinações, com a semente de cada um guardada junto.
    rng = random.Random(args.semente)
    cenarios = []
    for _ in range(args.n):
        cenarios.append((simular.sortear_cenario(rng), rng.randrange(1 << 30)))

    print("Calibrando contra %d eleições simuladas (erro aos 5%% apurado).\n"
          % args.n)
    print("  %-9s %-10s %-22s" % ("K_UF", "K_REGIAO", "erro médio / pior"))
    print("  " + "-" * 46)

    atual = (modelo.K_UF, modelo.K_REGIAO)
    melhor = None
    for k_uf in (60_000, 120_000, 180_000, 300_000, 600_000):
        for k_reg in (30_000, 90_000, 200_000):
            modelo.K_UF, modelo.K_REGIAO = float(k_uf), float(k_reg)
            med, pior = avaliar(mdl, ordem, cenarios)
            # Critério: média mais um peso no pior caso.
            nota = med + 0.5 * pior
            marca = ""
            if melhor is None or nota < melhor[0]:
                melhor = (nota, k_uf, k_reg, med, pior)
                marca = "  <--"
            atualmarca = "   (atual)" if (k_uf, k_reg) == atual else ""
            print("  %-9d %-10d %5.3f / %5.3f pp%s%s"
                  % (k_uf, k_reg, med, pior, marca, atualmarca))

    _, k_uf, k_reg, med, pior = melhor
    print("\nMelhor nos simulados: K_UF=%d  K_REGIAO=%d  (%.3f / %.3f pp)"
          % (k_uf, k_reg, med, pior))

    print("\nConferindo nas eleições reais:")
    for rotulo, (a, b) in (("atual", atual), ("novo", (k_uf, k_reg))):
        modelo.K_UF, modelo.K_REGIAO = float(a), float(b)
        linha = []
        for ano in (2018, 2022):
            if not os.path.exists(backtest.caminho_base(ano)):
                continue
            bs, seq = backtest.carregar(ano)
            ls, _ = backtest.rodar(bs, seq,
                                   passos=[p / 100.0 for p in range(1, 100, 3)])
            e = [abs(l["erro_proj"]) for l in ls if l["pct"] >= 5]
            linha.append("%d: méd %.2f máx %.2f" % (ano, sum(e) / len(e), max(e)))
        print("  %-6s K_UF=%-7d K_REGIAO=%-7d  %s"
              % (rotulo, a, b, "   ".join(linha)))

    print("\nSó troque se o ganho aparecer nos dois lugares. Um parâmetro que")
    print("melhora o simulado e piora o real está decorando o gerador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
