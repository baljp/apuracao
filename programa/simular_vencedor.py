"""
200 eleições cegas: com que frequência o modelo aponta o vencedor certo?

E, mais importante, a pergunta que realmente decide se dá para confiar nele
numa noite de apuração: **quando ele diz que tem 95% de certeza, ele acerta
95% das vezes?**

Um modelo que acerta muito mas é excessivamente confiante é perigoso — vai
cravar o lado errado numa eleição apertada e não terá dado nenhum aviso. Um
modelo que acerta um pouco menos mas sabe quando não sabe é útil, porque a
margem avisa quando não dá para concluir.

Por isso aqui se mede:

  1. acerto do vencedor, separado por quão apertada foi a eleição
  2. calibração: entre os casos em que o modelo deu X% de chance, em quantos
     ele de fato acertou
  3. erros graves: cravar (mais de 95% de confiança) no lado errado

Uso:
    python3 simular_vencedor.py                 200 cenários
    python3 simular_vencedor.py --n 500
"""

from __future__ import annotations

import argparse
import random
import sys

import modelo
import simular

MARCOS = [1, 5, 10, 20]


def rodar_um(mdl, ordem, cen, rng, n_bootstrap):
    alvo, verdade = simular.gerar_alvo(mdl, cen, rng)
    sequencia = [o for o in ordem if o["chave"] in mdl.por_chave]
    eleitorado = sum(mdl.por_chave[o["chave"]].eleitorado for o in sequencia)

    andamento, observado = {}, {}
    acc = 0.0
    i = 0
    saida = {}

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
        r = mdl.projetar(andamento, observado, n_bootstrap=n_bootstrap)
        bruto_pl = sum(o["pl"] for o in observado.values())
        bruto_tot = bruto_pl + sum(o["pt"] for o in observado.values())
        saida[marco] = {
            "proj": r["projecao_pl"],
            "prob": r.get("prob_pl"),
            "bruto": 100.0 * bruto_pl / bruto_tot,
        }
    return saida, verdade


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--calib", type=int, default=60,
                   help="quantos cenários rodam com bootstrap, para calibração")
    p.add_argument("--semente", type=int, default=777)
    args = p.parse_args()

    base, ordem = simular.carregar()
    mdl = modelo.Modelo(base)
    rng = random.Random(args.semente)

    print("%d eleições cegas sobre os %d municípios reais.\n"
          % (args.n, len(mdl.municipios)))

    res = []
    for k in range(args.n):
        cen = simular.sortear_cenario(rng)
        nb = 150 if k < args.calib else 0
        saida, verdade = rodar_um(mdl, ordem, cen, rng, nb)
        res.append((saida, verdade, nb > 0))
        if (k + 1) % 25 == 0:
            print("  %d/%d" % (k + 1, args.n), flush=True)

    # --- 1. acerto do vencedor -------------------------------------------
    print("\n  ACERTO DO VENCEDOR")
    print("  %-9s %-16s %s" % ("apurado", "modelo", "percentual bruto"))
    for marco in MARCOS:
        casos = [(s, v) for s, v, _ in res if marco in s]
        ok = sum(1 for s, v in casos if (s[marco]["proj"] > 50) == (v > 50))
        okb = sum(1 for s, v in casos if (s[marco]["bruto"] > 50) == (v > 50))
        print("  %6d%%    %3d/%-3d (%5.1f%%)   %3d/%-3d (%5.1f%%)"
              % (marco, ok, len(casos), 100.0 * ok / len(casos),
                 okb, len(casos), 100.0 * okb / len(casos)))

    # --- 2. acerto por aperto da eleição ---------------------------------
    print("\n  ACERTO AOS 5%, POR QUÃO APERTADA FOI A ELEIÇÃO")
    faixas = [(0, 0.5), (0.5, 1), (1, 2), (2, 5), (5, 100)]
    for lo, hi in faixas:
        casos = [(s, v) for s, v, _ in res
                 if 5 in s and lo <= abs(v - 50) < hi]
        if not casos:
            continue
        ok = sum(1 for s, v in casos if (s[5]["proj"] > 50) == (v > 50))
        rotulo = "diferença %g–%g pp" % (lo * 2, hi * 2) if hi < 100 \
            else "diferença acima de %g pp" % (lo * 2)
        print("  %-26s %3d/%-3d  (%5.1f%%)"
              % (rotulo, ok, len(casos), 100.0 * ok / len(casos)))

    # --- 3. calibração da probabilidade ----------------------------------
    com_prob = [(s, v) for s, v, teve in res if teve and 5 in s
                and s[5]["prob"] is not None]
    if com_prob:
        print("\n  CALIBRAÇÃO AOS 5%% (%d cenários com bootstrap)" % len(com_prob))
        print("  quando o modelo diz...      ele acerta")
        faixas_p = [(0.5, 0.7), (0.7, 0.9), (0.9, 0.99), (0.99, 1.01)]
        for lo, hi in faixas_p:
            sel = []
            for s, v in com_prob:
                prob = s[5]["prob"]
                # confiança no lado que ele aponta
                conf = prob if prob >= 0.5 else 1 - prob
                if lo <= conf < hi:
                    sel.append((s[5]["proj"] > 50) == (v > 50))
            if not sel:
                continue
            print("  %3.0f–%3.0f%% de certeza         %5.1f%%  (n=%d)"
                  % (lo * 100, hi * 100, 100.0 * sum(sel) / len(sel), len(sel)))

        graves = [(s, v) for s, v in com_prob
                  if (s[5]["prob"] > 0.95 or s[5]["prob"] < 0.05)
                  and (s[5]["proj"] > 50) != (v > 50)]
        print("\n  Erros graves (cravou acima de 95%% no lado errado): %d de %d"
              % (len(graves), len(com_prob)))
        for s, v in graves[:5]:
            print("    projetou %.2f%% com %.0f%% de certeza; real foi %.2f%%"
                  % (s[5]["proj"], 100 * max(s[5]["prob"], 1 - s[5]["prob"]), v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
