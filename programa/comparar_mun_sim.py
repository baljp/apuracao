"""Compara modelo atual x variante por município nos cenários simulados.
Uso: python3 comparar_mun_sim.py --n 2000 --semente 20261027 [--sem-nivel]"""
from __future__ import annotations
import argparse, json, random, sys
import modelo, modelo_mun, simular

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--semente", type=int, default=20261027)
    p.add_argument("--sem-nivel", action="store_true")
    p.add_argument("--saida", default=None)
    a = p.parse_args()
    base, ordem = simular.carregar()
    m0, m1 = modelo.Modelo(base), modelo_mun.ModeloMun(base)
    rng = random.Random(a.semente)
    seq = [o for o in ordem if o["chave"] in m0.por_chave]
    elei = sum(m0.por_chave[o["chave"]].eleitorado for o in seq)
    linhas = []
    for k in range(a.n):
        cen = simular.sortear_cenario(rng)
        if a.sem_nivel:
            cen["coef_nivel"] = 0.0
        alvo, verdade = simular.gerar_alvo(m0, cen, rng)
        andamento, obs, obs_mun = {}, {}, {}
        acc, i = 0.0, 0
        reg = {"id": k, "verdade": verdade, "cen": cen, "atual": {}, "mun": {}}
        for marco in simular.MARCOS:
            lim = marco / 100.0 * elei
            while i < len(seq) and acc < lim:
                ch = seq[i]["chave"]; m = m0.por_chave[ch]
                andamento[ch] = 1.0
                u = obs.setdefault(m.uf, {"pl": 0.0, "pt": 0.0})
                pl, pt = alvo[ch]; u["pl"] += pl; u["pt"] += pt
                obs_mun[ch] = (pl, pt)
                acc += m.eleitorado; i += 1
            if not obs: continue
            reg["atual"][str(marco)] = m0.projetar(andamento, obs, n_bootstrap=0)["projecao_pl"] - verdade
            reg["mun"][str(marco)] = m1.projetar(andamento, obs, obs_mun=obs_mun, n_bootstrap=0)["projecao_pl"] - verdade
        linhas.append(reg)
        if (k + 1) % 200 == 0: print("  %d/%d" % (k + 1, a.n), flush=True)
    if a.saida:
        json.dump(linhas, open(a.saida, "w"))
    ms = [str(m) for m in simular.MARCOS]
    print("\napurado   atual (médio/p90/pior)       variante por município (médio/p90/pior)")
    for m in ms:
        r = {}
        for nome in ("atual", "mun"):
            e = sorted(abs(l[nome][m]) for l in linhas if m in l[nome])
            r[nome] = (sum(e) / len(e), e[int(.9 * (len(e) - 1))], e[-1])
        print("%5s%%   %.2f / %.2f / %.2f          %.2f / %.2f / %.2f" % ((m,) + r["atual"] + r["mun"]))
    for m in ("1", "5", "10", "20"):
        for nome in ("atual", "mun"):
            err = sum(1 for l in linhas if (l["verdade"] > 50) != (l["verdade"] + l[nome][m] > 50))
            print("vencedor errado aos %s%% (%s): %d de %d (%.1f%%)" % (m, nome, err, len(linhas), 100 * err / len(linhas)))
main()
