"""
Testa o modelo em pares de eleições separadas por anos, não só entre turnos.

A pergunta: quanto a projeção depende de a base ser recente?

Entre dois turnos da mesma eleição, a base é quase perfeita — mesmos
eleitores, mesmas seções, três semanas de intervalo. Entre eleições separadas
por quatro anos, o eleitorado mudou, candidatos mudaram, o país mudou. Se o
modelo aguentar bem esse caso, é sinal de que ele apoia-se na geografia do
voto, que é estável, e não em detalhes que envelhecem.

Pares testados:

  1T 2022 -> 1T 2026    quatro anos, e com troca de candidato: Bolsonaro
                        saiu, Flávio entrou. É o teste mais duro que os
                        dados permitem montar.
  2T 2018 -> 2T 2022    quatro anos, mesmos finalistas de bloco.

Em todos, o número 22 é o campo da direita (Bolsonaro, depois Flávio) e o 13
é o do PT (Haddad, depois Lula), então o swing continua significando a mesma
coisa.

A ordem de chegada é sempre a real do 1º turno de 2026.

Uso:  python3 backtest_pares.py
"""

from __future__ import annotations

import json
import os
import sys

import backtest
import modelo

AQUI = os.path.dirname(os.path.abspath(__file__))


def ler(nome: str):
    caminho = os.path.join(AQUI, nome)
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)


def municipios_por_chave(dados, campo: str):
    """campo: 'votos' (1º turno daquele ano) ou 'alvo' (2º turno)."""
    saida = {}
    for m in dados["municipios"]:
        chave = "%s/%s" % (m["uf"], m["cd"])
        if campo == "votos":
            v = m.get("votos", {}) or {}
            pl, pt = float(v.get("22", 0)), float(v.get("13", 0))
        else:
            a = m.get("alvo", {}) or {}
            pl, pt = float(a.get("pl", 0)), float(a.get("pt", 0))
        if pl + pt > 0:
            saida[chave] = (pl, pt, m)
    return saida


def montar(base_dados, base_campo, alvo_dados, alvo_campo):
    """Monta o par no formato que o backtest entende."""
    base = municipios_por_chave(base_dados, base_campo)
    alvo = municipios_por_chave(alvo_dados, alvo_campo)
    comuns = set(base) & set(alvo)

    municipios = []
    for chave in comuns:
        bpl, bpt, bm = base[chave]
        apl, apt, am = alvo[chave]
        uf, cd = chave.split("/")
        municipios.append({
            "uf": uf, "cd": cd, "nm": bm.get("nm", ""),
            # O peso da apuração é o voto do ANO ALVO: é ele que entra nas
            # urnas na noite que estamos simulando.
            "eleitorado": int(apl + apt),
            "votos": {"22": bpl, "13": bpt},
            "votos_validos": bpl + bpt,
            "alvo": {"pl": apl, "pt": apt},
        })
    return {"municipios": municipios}, len(comuns)


def avaliar(rotulo, base_dados, base_campo, alvo_dados, alvo_campo):
    par, n = montar(base_dados, base_campo, alvo_dados, alvo_campo)
    if n < 1000:
        print("  %s: só %d municípios em comum, pulando" % (rotulo, n))
        return
    _, sequencia = None, None

    # Reaproveita a ordem real de chegada.
    with open(os.path.join(AQUI, "ordem_1t_2026.json"), encoding="utf-8") as fh:
        ordem = json.load(fh)["ordem"]
    por_chave = {"%s/%s" % (m["uf"], m["cd"]): m for m in par["municipios"]}
    sequencia = [por_chave[o["chave"]] for o in ordem if o["chave"] in por_chave]
    vistos = {("%s/%s" % (m["uf"], m["cd"])) for m in sequencia}
    sequencia += [m for k, m in por_chave.items() if k not in vistos]

    linhas, alvo_pct = backtest.rodar(par, sequencia, n_bootstrap=0)

    base_pl = sum(m["votos"]["22"] for m in par["municipios"])
    base_pt = sum(m["votos"]["13"] for m in par["municipios"])
    base_pct = 100.0 * base_pl / (base_pl + base_pt)

    print("\n=== %s ===" % rotulo)
    print("  %d municípios  |  base: %.2f%%  ->  real: %.2f%%  (swing de %+.2f pp)"
          % (n, base_pct, alvo_pct, alvo_pct - base_pct))
    print("  %-9s %-22s %s" % ("apurado", "percentual bruto", "projeção"))
    for marco in (1, 3, 5, 10, 20, 50):
        cand = [l for l in linhas if l["pct"] >= marco]
        if not cand:
            continue
        l = cand[0]
        print("  %6d%%   %6.2f%% (%+6.2f)      %6.2f%% (%+6.2f)"
              % (marco, l["bruto"], l["erro_bruto"], l["proj"], l["erro_proj"]))
    e5 = [abs(l["erro_proj"]) for l in linhas if l["pct"] >= 5]
    if e5:
        print("  a partir de 5%%: erro médio %.2f pp, máximo %.2f pp"
              % (sum(e5) / len(e5), max(e5)))


def main() -> int:
    b2018 = ler("base2018.json")
    b2022 = ler("base2022.json")
    b2026 = ler("base_1t.json")

    if not b2022 or not b2026:
        print("Faltam base2022.json e/ou base_1t.json")
        return 1

    print("Testes com base de anos anteriores (ordem de chegada real de 2026)")

    # O 1º turno de 2026 previsto a partir do 1º turno de 2022.
    avaliar("1º turno de 2022  ->  1º turno de 2026  (4 anos, troca de candidato)",
            b2022, "votos", b2026, "votos")

    if b2018:
        avaliar("2º turno de 2018  ->  2º turno de 2022  (4 anos)",
                b2018, "alvo", b2022, "alvo")

    print("\nPara comparar, com base do MESMO ano (três semanas de intervalo):")
    print("  2º turno de 2022: erro médio 0,07 pp, máximo 0,24 pp")
    print("  2º turno de 2018: erro médio 1,10 pp, máximo 1,98 pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
