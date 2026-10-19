"""
Testa a vulnerabilidade que nenhum outro teste deste projeto cobre:
município apurado pela metade, com a metade errada.

Todos os backtests daqui fazem o município entrar inteiro, de uma vez. Na
noite real não é assim: São Paulo tem 26.683 seções e fica horas
parcialmente apurado. E o modelo assume, ao calcular o esperado, que a
parcela já apurada de um município REPRESENTA aquele município.

Se as seções chegassem em ordem aleatória, a premissa seria boa. Mas não
chegam: as seções menores, de zona rural e de bairros periféricos, costumam
fechar antes das grandes urbanas — e votam diferente. Esse é um viés de
composição DENTRO do município, invisível para o modelo, porque os arquivos
do TSE só dizem quanto do eleitorado já foi totalizado, não quais seções.

Aqui cada município é dividido em duas partes com voto diferente ("interior"
e "centro"), e o interior apura primeiro. A diferença entre as duas partes é
controlada por --divergencia, em log-odds:

    0.0   as duas partes votam igual (equivale aos testes anteriores)
    0.3   diferença moderada, do tamanho da que se vê entre bairros
    0.6   diferença forte, do tamanho da que separa capital de interior

Uso:
    python3 simular_parcial.py
    python3 simular_parcial.py --divergencia 0.6
"""

from __future__ import annotations

import argparse
import random
import sys

import modelo
import simular

MARCOS = [1, 3, 5, 10, 20, 50]


def rodar_um(mdl, ordem, cen, rng, divergencia):
    """
    Como os anteriores, mas cada município apura em duas levas: primeiro a
    parte 'interior', depois a 'centro'.
    """
    alvo_mun, verdade = simular.gerar_alvo(mdl, cen, rng)

    # Divide cada município em duas partes. A fração que é "interior" e o
    # quanto ela diverge variam de lugar para lugar.
    partes = {}
    for m in mdl.municipios:
        pl, pt = alvo_mun[m.chave]
        total = pl + pt
        if total <= 0:
            continue
        frac_interior = rng.uniform(0.25, 0.55)
        delta = rng.gauss(divergencia, divergencia * 0.4)
        s_total = pl / total
        # Desloca o voto das duas partes em direções opostas, mantendo o
        # total do município intacto.
        lo = modelo._logit(pl, pt)
        s_int = modelo._share(lo + delta)
        s_cen = modelo._share(lo - delta * frac_interior / (1 - frac_interior))
        v_int = total * frac_interior
        v_cen = total - v_int
        # Reequilibra para o total do município bater exatamente.
        soma_pl = v_int * s_int + v_cen * s_cen
        ajuste = (pl - soma_pl) / total if total else 0.0
        partes[m.chave] = [
            (v_int, min(max(s_int + ajuste, 0.0), 1.0)),
            (v_cen, min(max(s_cen + ajuste, 0.0), 1.0)),
        ]

    sequencia = [o for o in ordem if o["chave"] in mdl.por_chave]
    eleitorado = sum(mdl.por_chave[o["chave"]].eleitorado for o in sequencia)

    # A ordem de chegada, do jeito realista: cada município apura primeiro o
    # interior e depois o centro, mas o atraso entre as duas partes é
    # proporcional ao TAMANHO do município. Uma cidade de 3 mil eleitores
    # fecha as duas partes quase junto; São Paulo leva horas entre uma e
    # outra, e nesse meio-tempo centenas de cidades pequenas fecham inteiras.
    #
    # Fazer todos os interiores do país entrarem antes de qualquer centro,
    # como numa primeira versão deste teste, produz um viés que não existe na
    # realidade e superestima muito o problema.
    maior = max((mdl.por_chave[o["chave"]].eleitorado for o in sequencia),
                default=1) or 1
    fila = []
    for posicao, o in enumerate(sequencia):
        chave = o["chave"]
        if chave not in partes:
            continue
        m = mdl.por_chave[chave]
        atraso = (m.eleitorado / maior) * len(sequencia) * 0.5
        fila.append((posicao, chave, 0))
        fila.append((posicao + atraso, chave, 1))
    fila.sort(key=lambda x: x[0])
    fila = [(chave, qual) for _, chave, qual in fila]

    andamento, observado = {}, {}
    acc = 0.0
    i = 0
    saida = {}

    for marco in MARCOS:
        limite = (marco / 100.0) * eleitorado
        while i < len(fila) and acc < limite:
            chave, qual = fila[i]
            m = mdl.por_chave[chave]
            v, s = partes[chave][qual]
            uf = observado.setdefault(m.uf, {"pl": 0.0, "pt": 0.0})
            uf["pl"] += v * s
            uf["pt"] += v * (1 - s)
            # Fração do eleitorado do município que esta parte representa.
            total_v = partes[chave][0][0] + partes[chave][1][0]
            andamento[chave] = andamento.get(chave, 0.0) + (v / total_v)
            acc += m.eleitorado * (v / total_v)
            i += 1
        if not observado:
            continue
        r = mdl.projetar(andamento, observado, n_bootstrap=0)
        saida[marco] = r["projecao_pl"] - verdade
    return saida, verdade


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--divergencia", type=float, default=None)
    p.add_argument("--semente", type=int, default=4242)
    args = p.parse_args()

    base, ordem = simular.carregar()
    mdl = modelo.Modelo(base)

    divergencias = ([args.divergencia] if args.divergencia is not None
                    else [0.0, 0.3, 0.6])

    print("Municípios apurando pela metade, com a metade enviesada.")
    print("%d cenários por nível de divergência.\n" % args.n)
    print("  %-14s %s" % ("divergência", "erro médio da projeção, por % apurado"))
    print("  %-14s %s" % ("", "   ".join("%5d%%" % m for m in MARCOS)))
    print("  " + "-" * 62)

    for div in divergencias:
        rng = random.Random(args.semente)
        acum = {m: [] for m in MARCOS}
        for _ in range(args.n):
            cen = simular.sortear_cenario(rng)
            saida, _ = rodar_um(mdl, ordem, cen, rng, div)
            for m, e in saida.items():
                acum[m].append(abs(e))
        rotulo = ("%.1f (igual)" % div if div == 0 else
                  "%.1f (moderada)" % div if div < 0.5 else
                  "%.1f (forte)" % div)
        print("  %-14s %s"
              % (rotulo,
                 "   ".join("%5.2f" % (sum(acum[m]) / len(acum[m]))
                            if acum[m] else "    —" for m in MARCOS)))

    print("\n  Se a linha de divergência forte não se afastar muito da de")
    print("  divergência zero, o esperado composicional está aguentando o")
    print("  viés dentro do município. Se se afastar, essa é a maior")
    print("  fragilidade do modelo na noite real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
