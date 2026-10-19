"""
Varre a força da regressão do swing sobre o nível, medindo nos dois anos.

A pergunta: deixar o modelo aprender que "onde o candidato era forte ele caiu
mais" ajuda em 2018 sem estragar 2022?

LAMBDA_NIVEL é o freio. Alto demais, o coeficiente fica perto de zero e nada
muda; baixo demais, a reta persegue ruído com poucos estados apurados e o
modelo inventa padrão onde não há.

Uso:  python3 testar_nivel.py
"""

from __future__ import annotations

import os
import sys

import backtest
import modelo

ANOS = (2018, 2022)


def erros(ano: int, desde: float = 2.0):
    base, sequencia = backtest.carregar(ano)
    linhas, _ = backtest.rodar(base, sequencia,
                               passos=[p / 100.0 for p in range(1, 100, 3)])
    e = [abs(l["erro_proj"]) for l in linhas if l["pct"] >= desde]
    return (sum(e) / len(e), max(e)) if e else (99.0, 99.0)


def main() -> int:
    for ano in ANOS:
        if not os.path.exists(backtest.caminho_base(ano)):
            print("Falta base%d.json" % ano)
            return 1

    print("Força da regressão do swing sobre o nível do lugar.")
    print("(coeficiente verdadeiro em 2018, medido com tudo apurado: -0,140)\n")
    print("  %-10s %-10s %-16s %-16s %s"
          % ("λ", "limite", "2018 méd/máx", "2022 méd/máx", "pior"))
    print("  " + "-" * 68)

    melhor = None
    # desligado, para referência
    modelo.USAR_REGRESSAO_NIVEL = False
    r = {a: erros(a) for a in ANOS}
    pior = max(r[a][1] for a in ANOS)
    print("  %-10s %-10s %5.2f / %5.2f    %5.2f / %5.2f     %5.2f   (desligado)"
          % ("—", "—", r[2018][0], r[2018][1], r[2022][0], r[2022][1], pior))
    base_ref = pior

    modelo.USAR_REGRESSAO_NIVEL = True
    for lam in (0.02, 0.05, 0.10, 0.20, 0.40):
        for lim in (0.15, 0.30, 0.60):
            modelo.LAMBDA_NIVEL = lam
            modelo.LIMITE_AJUSTE_NIVEL = lim
            r = {a: erros(a) for a in ANOS}
            pior = max(r[a][1] for a in ANOS)
            marca = ""
            if melhor is None or pior < melhor[0]:
                melhor = (pior, lam, lim, dict(r))
                marca = "  <--"
            print("  %-10.2f %-10.2f %5.2f / %5.2f    %5.2f / %5.2f     %5.2f%s"
                  % (lam, lim, r[2018][0], r[2018][1],
                     r[2022][0], r[2022][1], pior, marca))

    pior, lam, lim, r = melhor
    print("\nMelhor: λ=%.2f  limite=%.2f" % (lam, lim))
    print("  2018: médio %.2f pp, máximo %.2f pp" % r[2018])
    print("  2022: médio %.2f pp, máximo %.2f pp" % r[2022])
    print("\nSem a regressão, o pior caso era %.2f pp. Com ela, %.2f pp."
          % (base_ref, pior))
    print("Só vale ligar se o ganho for claro; se for empate, fica desligada,")
    print("porque menos peça móvel é menos coisa para dar errado no dia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
