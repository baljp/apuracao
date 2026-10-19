"""
Prepara o par 1º turno -> 2º turno de 2022 para o backtest.

Lê a votação por seção eleitoral de 2022 publicada nos dados abertos do TSE
(1,6 GB) e agrega por município, separando os dois turnos. O resultado é um
arquivo pequeno (base2022.json) com, para cada município: quanto votou, como
votou no 1º turno, e o resultado real do 2º turno.

Com isso o backtest tem tudo: uma base (1º turno), um alvo conhecido
(2º turno) e uma ordem de chegada realista.

Uso:  python3 preparar_2022.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
ZIP = os.path.join(AQUI, "dados2022", "votacao_secao_2022_BR.zip")
SAIDA = os.path.join(AQUI, "base2022.json")

# Em 2022 os finalistas foram Lula (13) e Jair Bolsonaro (22).
NUM_PL = "22"
NUM_PT = "13"


def main() -> int:
    if not os.path.exists(ZIP):
        print("Arquivo não encontrado: %s" % ZIP)
        print("Baixe antes (271 MB):")
        print("  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/"
              "votacao_secao_2022_BR.zip")
        return 1

    muns: dict = {}
    inicio = time.time()
    linhas = 0

    with zipfile.ZipFile(ZIP) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        print("Lendo %s (1,6 GB descompactado)..." % nome, flush=True)
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            cab = [c.strip().strip('"') for c in texto.readline().split(";")]
            idx = {c: i for i, c in enumerate(cab)}
            i_turno = idx["NR_TURNO"]
            i_uf = idx["SG_UF"]
            i_mun = idx["CD_MUNICIPIO"]
            i_nm = idx["NM_MUNICIPIO"]
            i_cargo = idx["CD_CARGO"]
            i_votavel = idx["NR_VOTAVEL"]
            i_votos = idx["QT_VOTOS"]
            largura = len(cab)

            for linha in texto:
                linhas += 1
                if (linhas & 0x3FFFFF) == 0:
                    print("    %d milhões de linhas (%.0fs)"
                          % (linhas // 1_000_000, time.time() - inicio), flush=True)
                campos = linha.split(";")
                if len(campos) < largura:
                    continue
                if campos[i_cargo].strip('"') != "1":
                    continue
                try:
                    votos = int(campos[i_votos].strip('" \n\r') or 0)
                except ValueError:
                    continue

                cd = campos[i_mun].strip('"')
                m = muns.get(cd)
                if m is None:
                    m = muns[cd] = {
                        "uf": campos[i_uf].strip('"').lower(),
                        "nm": campos[i_nm].strip('"'),
                        "t1": {}, "t2": {},
                    }
                alvo = m["t1"] if campos[i_turno].strip('"') == "1" else m["t2"]
                votavel = campos[i_votavel].strip('"')
                alvo[votavel] = alvo.get(votavel, 0) + votos

    print("  %d linhas lidas em %.0fs" % (linhas, time.time() - inicio), flush=True)

    saida = []
    for cd, m in muns.items():
        t1, t2 = m["t1"], m["t2"]
        pl1, pt1 = t1.get(NUM_PL, 0), t1.get(NUM_PT, 0)
        pl2, pt2 = t2.get(NUM_PL, 0), t2.get(NUM_PT, 0)
        if pl1 + pt1 == 0 or pl2 + pt2 == 0:
            continue
        # Votos nominais válidos do 1º turno (números de candidato têm 2
        # dígitos; branco=95, nulo=96 e afins ficam de fora).
        validos1 = sum(v for n, v in t1.items()
                       if n.isdigit() and len(n) == 2 and int(n) < 90)
        saida.append({
            "uf": m["uf"],
            "cd": cd,
            "nm": m["nm"],
            # O peso da apuração é quanta gente votou — é isso que entra nas
            # urnas e define o ritmo da totalização.
            "eleitorado": pl2 + pt2 + sum(
                v for n, v in t2.items()
                if n.isdigit() and len(n) == 2 and int(n) >= 90),
            # Todos os candidatos do 1º turno, não só os dois finalistas: o
            # peso dos eliminados em cada município é o que permite ao modelo
            # perceber que a transferência de votos não foi igual em todo lugar.
            "votos": {n: v for n, v in t1.items()
                      if n.isdigit() and len(n) == 2 and int(n) < 90},
            "votos_validos": validos1,
            "alvo": {"pl": pl2, "pt": pt2},
        })

    total_pl = sum(m["alvo"]["pl"] for m in saida)
    total_pt = sum(m["alvo"]["pt"] for m in saida)
    with open(SAIDA, "w", encoding="utf-8") as fh:
        json.dump({"municipios": saida}, fh, ensure_ascii=False)

    print("\nSalvo em %s" % SAIDA)
    print("  municípios: %d" % len(saida))
    print("  2º turno de 2022 reconstruído:  Bolsonaro %.2f%%   Lula %.2f%%"
          % (100.0 * total_pl / (total_pl + total_pt),
             100.0 * total_pt / (total_pl + total_pt)))
    print("  resultado oficial do TSE:       Bolsonaro 49,10%   Lula 50,90%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
