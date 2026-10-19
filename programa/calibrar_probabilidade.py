"""
A confiança que o modelo declara corresponde à realidade?

Duas perguntas diferentes, e as duas importam numa noite de apuração:

  1. quando o painel diz "95% de chance de vitória de fulano", fulano ganha
     95% das vezes?
  2. quando o painel mostra uma faixa de 90%, o resultado cai dentro dela
     90% das vezes?

Um modelo confiante demais é perigoso: vai cravar o lado errado numa eleição
apertada sem ter dado aviso nenhum. Um modelo tímido demais é inútil: nunca
conclui nada. O que se quer é que o número declarado signifique o que diz.

Este teste roda só em **eleições apertadas**, de propósito. Numa eleição
decidida por 10 pontos qualquer modelo diz 99,9% e acerta — isso não ensina
nada sobre calibração. O swing nacional de cada cenário é escolhido para que
o resultado caia perto de 50%, que é onde a probabilidade é posta à prova.

Uso:
    python3 calibrar_probabilidade.py --n 300
    python3 calibrar_probabilidade.py --n 300 --sigma 0.045   (testa outro σ)
"""

from __future__ import annotations

import argparse
import random
import sys

import modelo
import simular

MARCO = 5  # a calibração é medida aos 5% apurado


def cenario_apertado(rng: random.Random, mdl, alvo_pct: float) -> dict:
    """
    Um cenário cujo resultado final cai perto de alvo_pct.

    Os outros ingredientes (desigualdade regional, dependência do nível,
    choque estadual, ruído) continuam sorteados como sempre: só o swing
    nacional é escolhido para mirar o alvo.
    """
    cen = simular.sortear_cenario(rng)
    cen["nacional"] = mdl.swing_das_pesquisas(alvo_pct)
    return cen


def rodar_um(mdl, ordem, cen, rng, n_bootstrap):
    alvo, verdade = simular.gerar_alvo(mdl, cen, rng)
    sequencia = [o for o in ordem if o["chave"] in mdl.por_chave]
    eleitorado = sum(mdl.por_chave[o["chave"]].eleitorado for o in sequencia)

    andamento, observado = {}, {}
    acc = 0.0
    limite = (MARCO / 100.0) * eleitorado
    for item in sequencia:
        if acc >= limite:
            break
        chave = item["chave"]
        m = mdl.por_chave[chave]
        andamento[chave] = 1.0
        uf = observado.setdefault(m.uf, {"pl": 0.0, "pt": 0.0})
        pl, pt = alvo[chave]
        uf["pl"] += pl
        uf["pt"] += pt
        acc += m.eleitorado

    r = mdl.projetar(andamento, observado, n_bootstrap=n_bootstrap)
    return r, verdade


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--bootstrap", type=int, default=150)
    p.add_argument("--sigma", type=float, default=None,
                   help="sobrescreve SIGMA_SWING, para testar outra largura")
    p.add_argument("--semente", type=int, default=31337)
    args = p.parse_args()

    if args.sigma is not None:
        modelo.SIGMA_SWING = args.sigma

    base, ordem = simular.carregar()
    mdl = modelo.Modelo(base)
    rng = random.Random(args.semente)

    print("%d eleições apertadas, medindo a confiança declarada aos %d%% apurado."
          % (args.n, MARCO))
    print("SIGMA_SWING = %.3f\n" % modelo.SIGMA_SWING)

    registros = []
    for k in range(args.n):
        # Resultado final mirando entre 48,5% e 51,5%.
        alvo_pct = rng.uniform(48.5, 51.5)
        cen = cenario_apertado(rng, mdl, alvo_pct)
        r, verdade = rodar_um(mdl, ordem, cen, rng, args.bootstrap)
        prob = r["prob_pl"]
        confianca = prob if r["projecao_pl"] > 50 else 1 - prob
        registros.append({
            "proj": r["projecao_pl"],
            "verdade": verdade,
            "acertou": (r["projecao_pl"] > 50) == (verdade > 50),
            "confianca": confianca,
            "faixa": r["faixa_pl"],
            "dentro": r["faixa_pl"][0] <= verdade <= r["faixa_pl"][1],
            "largura": r["faixa_pl"][1] - r["faixa_pl"][0],
        })
        if (k + 1) % 50 == 0:
            print("  %d/%d" % (k + 1, args.n), flush=True)

    # --- calibração da probabilidade -------------------------------------
    print("\n  CALIBRAÇÃO DA PROBABILIDADE")
    print("  %-22s %-12s %-10s %s" % ("quando diz...", "acerta", "n", "veredito"))
    faixas = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90),
              (0.90, 0.95), (0.95, 0.99), (0.99, 1.001)]
    for lo, hi in faixas:
        sel = [r for r in registros if lo <= r["confianca"] < hi]
        if len(sel) < 5:
            continue
        real = sum(1 for r in sel if r["acertou"]) / len(sel)
        esperado = (lo + min(hi, 1.0)) / 2
        dif = real - esperado
        veredito = ("bem calibrado" if abs(dif) < 0.07 else
                    "confiante demais" if dif < 0 else "tímido demais")
        print("  %3.0f–%3.0f%% de certeza      %5.1f%%       %-10d %s (%+.0f pp)"
              % (lo * 100, min(hi, 1.0) * 100, 100 * real, len(sel),
                 veredito, 100 * dif))

    # --- cobertura do intervalo ------------------------------------------
    dentro = sum(1 for r in registros if r["dentro"])
    largura = sum(r["largura"] for r in registros) / len(registros)
    print("\n  COBERTURA DA FAIXA DE 90%")
    print("  o resultado real caiu dentro da faixa em %.1f%% dos casos "
          "(esperado: 90%%)" % (100.0 * dentro / len(registros)))
    print("  largura média da faixa: %.2f pontos" % largura)
    if 100.0 * dentro / len(registros) < 85:
        print("  -> faixa ESTREITA demais: o site promete mais precisão do que tem")
    elif 100.0 * dentro / len(registros) > 95:
        print("  -> faixa LARGA demais: o site é mais vago do que precisaria")
    else:
        print("  -> faixa adequada")

    # --- erros graves -----------------------------------------------------
    graves = [r for r in registros if r["confianca"] > 0.95 and not r["acertou"]]
    print("\n  Cravou acima de 95%% no lado errado: %d de %d (%.1f%%)"
          % (len(graves), len(registros), 100.0 * len(graves) / len(registros)))
    for r in graves[:5]:
        print("    projetou %.2f%% com %.0f%% de certeza; real foi %.2f%%"
              % (r["proj"], 100 * r["confianca"], r["verdade"]))

    erro = sum(abs(r["proj"] - r["verdade"]) for r in registros) / len(registros)
    print("\n  (erro médio da projeção nestes cenários apertados: %.2f pp)" % erro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
