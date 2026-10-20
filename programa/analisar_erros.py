"""
Roda N eleições cegas (mesmo gerador do simular.py) e guarda CADA cenário,
para responder: quando o modelo errou o vencedor, e que tipo de mundo era.

Uso:  python3 analisar_erros.py --n 2000 --semente 20261027 --saida erros.json
"""
from __future__ import annotations
import argparse, json, random, sys
import modelo
import simular


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--semente", type=int, default=20261027)
    p.add_argument("--saida", default="erros.json")
    a = p.parse_args()

    base, ordem = simular.carregar()
    mdl = modelo.Modelo(base)
    rng = random.Random(a.semente)
    linhas = []
    for k in range(a.n):
        cen = simular.sortear_cenario(rng)
        erros, verdade, cen = simular.rodar_cenario(mdl, ordem, cen, rng)
        linhas.append({
            "id": k, "verdade": verdade, "cen": cen,
            "proj": {str(m): v["proj"] for m, v in erros.items()},
            "bruto": {str(m): v["bruto"] for m, v in erros.items()},
        })
        if (k + 1) % 100 == 0:
            print("  %d/%d" % (k + 1, a.n), flush=True)
    with open(a.saida, "w") as fh:
        json.dump(linhas, fh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
