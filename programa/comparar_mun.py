"""
Compara o modelo atual (swing por estado) com a variante por município
(modelo_mun.py) nas cinco eleições históricas, com a ordem real de chegada.

Uso:  python3 comparar_mun.py [--anos 2006 2010 ...]
"""
from __future__ import annotations
import sys
import backtest
import modelo
import modelo_mun

MARCOS = [1, 2, 3, 5, 10, 20, 50]
ANOS = [2006, 2010, 2014, 2018, 2022]


def curva(classe, ano, base=None, seq=None):
    if base is None:
        base, seq = backtest.carregar(ano)
    mdl = classe(base)
    alvo = backtest.resultado_final(base)
    total = sum(m["eleitorado"] for m in seq)
    andamento, observado, obs_mun = {}, {}, {}
    acc, i = 0.0, 0
    out = {}
    for marco in MARCOS:
        lim = marco / 100.0 * total
        while i < len(seq) and acc < lim:
            m = seq[i]
            ch = "%s/%s" % (m["uf"], m["cd"])
            andamento[ch] = 1.0
            u = observado.setdefault(m["uf"], {"pl": 0.0, "pt": 0.0})
            u["pl"] += m["alvo"]["pl"]; u["pt"] += m["alvo"]["pt"]
            obs_mun[ch] = (m["alvo"]["pl"], m["alvo"]["pt"])
            acc += m["eleitorado"]; i += 1
        kw = {"obs_mun": obs_mun} if classe is modelo_mun.ModeloMun else {}
        r = mdl.projetar(andamento, observado, n_bootstrap=0, **kw)
        out[marco] = r["projecao_pl"] - alvo
    return out, alvo


def main():
    anos = ANOS
    if "--anos" in sys.argv:
        anos = [int(a) for a in sys.argv[sys.argv.index("--anos") + 1:]]
    print("erro absoluto da projeção (pp) por % apurado")
    print("%-6s %-5s " % ("ano", "mod") + " ".join("%5d%%" % m for m in MARCOS) + "   média")
    tot = {"atual": [], "mun": []}
    for ano in anos:
        base, seq = backtest.carregar(ano)
        for nome, cls in (("atual", modelo.Modelo), ("mun", modelo_mun.ModeloMun)):
            e, alvo = curva(cls, ano, base, seq)
            v = [abs(e[m]) for m in MARCOS]
            tot[nome].append(v)
            print("%-6d %-5s " % (ano, nome) + " ".join("%6.2f" % x for x in v)
                  + "   %5.2f" % (sum(v) / len(v)))
    print()
    for nome in tot:
        n = len(tot[nome])
        med = [sum(r[j] for r in tot[nome]) / n for j in range(len(MARCOS))]
        print("%-12s " % ("MÉDIA " + nome) + " ".join("%6.2f" % x for x in med)
              + "   %5.2f" % (sum(med) / len(med)))


if __name__ == "__main__":
    main()
