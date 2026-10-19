"""
Quanto custa ler o andamento mais devagar que os votos?

Motivo da pergunta: dos 4,8 MB que uma leitura completa do TSE traz, 4,55 MB
estão num arquivo só — o andamento por município (-ab.json, 5.570 municípios).
O arquivo de votos, que é o que de fato muda o resultado, pesa 246 KB.

Se o andamento puder ser lido a cada dois minutos em vez de a cada vinte e
cinco segundos, o tráfego cai cerca de 95% sem tocar na frequência com que os
VOTOS chegam à tela. A dúvida é se isso estraga a projeção, e isso não se
decide no achismo.

O modelo usa o andamento para saber quanto de cada município já foi apurado,
e daí calcular o valor esperado — a conta que neutraliza o fato de o Sul
apurar antes do Nordeste. Ler o andamento com atraso significa o modelo achar
que apurou MENOS do que apurou, e atribuir ao esperado um peso errado.

Aqui o andamento é congelado num ponto anterior da noite enquanto os votos
seguem chegando, e mede-se o erro da projeção com e sem esse atraso.

A defasagem é dada em pontos percentuais do eleitorado, porque é assim que o
modelo enxerga o tempo. Para converter: numa noite real a apuração anda perto
de 2 pontos por minuto no pico, então

    0,8 pp  ≈  25 segundos
    2,0 pp  ≈   1 minuto
    4,0 pp  ≈   2 minutos
   10,0 pp  ≈   5 minutos

Uso:
    python3 testar_defasagem.py
    python3 testar_defasagem.py --ano 2018
"""

from __future__ import annotations

import argparse
import sys

import backtest
import modelo

MARCOS = [1, 2, 3, 5, 10, 20, 50]
DEFASAGENS = [0.0, 0.8, 2.0, 4.0, 10.0]


def rodar_com_defasagem(base, sequencia, defasagem_pp):
    """
    Igual ao backtest normal, com uma diferença: o andamento só registra os
    municípios que já tinham entrado `defasagem_pp` pontos atrás. Os votos
    continuam entrando no instante certo — é exatamente o descompasso que
    existiria se o -ab.json fosse buscado com menos frequência que o -u.json.
    """
    mdl = modelo.Modelo(base)
    alvo = backtest.resultado_final(base)
    eleitorado_total = sum(m["eleitorado"] for m in sequencia)

    andamento, observado = {}, {}
    acumulado = 0.0
    i = 0          # até onde os VOTOS chegaram
    j = 0          # até onde o ANDAMENTO conhecido chegou
    acumulado_j = 0.0
    linhas = []

    for alvo_frac in [p / 100.0 for p in range(1, 100)]:
        limite = alvo_frac * eleitorado_total
        while i < len(sequencia) and acumulado < limite:
            m = sequencia[i]
            uf = observado.setdefault(m["uf"], {"pl": 0.0, "pt": 0.0})
            uf["pl"] += m["alvo"]["pl"]
            uf["pt"] += m["alvo"]["pt"]
            acumulado += m["eleitorado"]
            i += 1

        # O andamento fica para trás pelo tanto de eleitorado que a
        # defasagem representa.
        atraso = defasagem_pp / 100.0 * eleitorado_total
        while j < i and acumulado_j < acumulado - atraso:
            m = sequencia[j]
            andamento["%s/%s" % (m["uf"], m["cd"])] = 1.0
            acumulado_j += m["eleitorado"]
            j += 1

        if not andamento:
            continue
        soma = sum(u["pl"] + u["pt"] for u in observado.values())
        if soma == 0:
            continue
        r = mdl.projetar(andamento, observado, n_bootstrap=0)
        linhas.append((r["pct_apurado"], abs(r["projecao_pl"] - alvo)))
    return linhas


def erro_em(linhas, marco):
    """Erro no primeiro ponto em que o apurado alcançou o marco."""
    for pct, err in linhas:
        if pct >= marco:
            return err
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2022)
    args = ap.parse_args()

    base, sequencia = backtest.carregar(args.ano)
    print("\n  Erro da projeção (pontos percentuais), eleição de %d" % args.ano)
    print("  Cada linha atrasa o andamento; os votos chegam sempre na hora.\n")
    print("     atraso          " + "".join("%8s" % ("%d%%" % m) for m in MARCOS))
    print("  " + "-" * (20 + 8 * len(MARCOS)))

    base_linhas = None
    for d in DEFASAGENS:
        linhas = rodar_com_defasagem(base, sequencia, d)
        if base_linhas is None:
            base_linhas = linhas
        seg = "  —" if d == 0 else "~%ds" % round(d / 2.0 * 60)
        rotulo = "sem atraso" if d == 0 else "%.1f pp (%s)" % (d, seg.strip())
        valores = ""
        for m in MARCOS:
            e = erro_em(linhas, m)
            valores += "%8s" % ("—" if e is None else "%.2f" % e)
        print("  %-18s%s" % (rotulo, valores))

    # Pior degradação observada em qualquer marco, por defasagem.
    print()
    for d in DEFASAGENS[1:]:
        linhas = rodar_com_defasagem(base, sequencia, d)
        pior = 0.0
        for m in MARCOS:
            a, b = erro_em(base_linhas, m), erro_em(linhas, m)
            if a is not None and b is not None:
                pior = max(pior, b - a)
        print("  atraso de %4.1f pp: piora no máximo %+.2f pp" % (d, pior))
    return 0


if __name__ == "__main__":
    sys.exit(main())
