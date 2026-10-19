"""
Prepara o par 1º turno -> 2º turno de uma eleição passada, para o backtest.

Lê a votação por seção eleitoral publicada nos dados abertos do TSE e agrega
por município, separando os dois turnos. O resultado é um arquivo pequeno com,
para cada município: quanto votou, como votou no 1º turno (todos os
candidatos) e o resultado real do 2º turno.

Uso:
    python3 preparar_historico.py --ano 2022
    python3 preparar_historico.py --ano 2018

Antes, baixe o arquivo correspondente para dados<ano>/:
    https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_<ano>_BR.zip
"""

from __future__ import annotations

import argparse
import io
import os
import json
import sys
import time
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))

# Os dois que foram ao 2º turno em cada eleição, e o resultado oficial, para
# conferir que a reconstrução a partir das seções bate com o que o TSE publicou.
# Em todas, "a" é o candidato que não é do PT e "b" é o do PT — que foram os
# dois blocos de todos os segundos turnos presidenciais desde 2006. O número
# do partido muda (45 do PSDB até 2014, 17 e 22 depois), mas o papel no modelo
# é o mesmo, então os dois são gravados sempre como 22 e 13.
ELEICOES = {
    2006: {"a": "45", "b": "13", "nome_a": "Alckmin", "nome_b": "Lula",
           "oficial_a": 39.17, "oficial_b": 60.83},
    2010: {"a": "45", "b": "13", "nome_a": "Serra", "nome_b": "Dilma",
           "oficial_a": 43.95, "oficial_b": 56.05},
    2014: {"a": "45", "b": "13", "nome_a": "Aécio", "nome_b": "Dilma",
           "oficial_a": 48.36, "oficial_b": 51.64},
    2018: {"a": "17", "b": "13", "nome_a": "Bolsonaro", "nome_b": "Haddad",
           "oficial_a": 55.13, "oficial_b": 44.87},
    2022: {"a": "22", "b": "13", "nome_a": "Bolsonaro", "nome_b": "Lula",
           "oficial_a": 49.10, "oficial_b": 50.90},
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ano", type=int, default=2022, choices=sorted(ELEICOES))
    args = p.parse_args()
    cfg = ELEICOES[args.ano]
    num_a, num_b = cfg["a"], cfg["b"]

    zip_path = os.path.join(AQUI, "dados%d" % args.ano,
                            "votacao_secao_%d_BR.zip" % args.ano)
    saida = os.path.join(AQUI, "base%d.json" % args.ano)

    if not os.path.exists(zip_path):
        print("Arquivo não encontrado: %s" % zip_path)
        print("Baixe antes:")
        print("  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/"
              "votacao_secao_%d_BR.zip" % args.ano)
        return 1

    muns: dict = {}
    inicio = time.time()
    linhas = 0

    with zipfile.ZipFile(zip_path) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        print("Lendo %s..." % nome, flush=True)
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
                    m = muns[cd] = {"uf": campos[i_uf].strip('"').lower(),
                                    "nm": campos[i_nm].strip('"'),
                                    "t1": {}, "t2": {}}
                alvo = m["t1"] if campos[i_turno].strip('"') == "1" else m["t2"]
                v = campos[i_votavel].strip('"')
                alvo[v] = alvo.get(v, 0) + votos

    print("  %d linhas lidas em %.0fs" % (linhas, time.time() - inicio), flush=True)

    def nominal(d):
        return {n: v for n, v in d.items()
                if n.isdigit() and len(n) == 2 and int(n) < 90}

    lista = []
    for cd, m in muns.items():
        t1, t2 = m["t1"], m["t2"]
        a1, b1 = t1.get(num_a, 0), t1.get(num_b, 0)
        a2, b2 = t2.get(num_a, 0), t2.get(num_b, 0)
        if a1 + b1 == 0 or a2 + b2 == 0:
            continue
        nom1 = nominal(t1)
        lista.append({
            "uf": m["uf"], "cd": cd, "nm": m["nm"],
            "eleitorado": sum(t2.values()),
            # Os votos do 1º turno são gravados sob os números de 2026 (22 e
            # 13), porque é assim que o modelo os procura. O que importa para
            # o backtest é a identidade "finalista A" e "finalista B", não o
            # número do partido naquele ano.
            "votos": dict(nom1, **{"22": a1, "13": b1})
                     if num_a not in ("22", "13") else
                     {("22" if n == num_a else "13" if n == num_b else n): v
                      for n, v in nom1.items()},
            "votos_validos": sum(nom1.values()),
            "alvo": {"pl": a2, "pt": b2},
        })

    # Quando o finalista tinha outro número (2018: Bolsonaro era 17), o voto
    # dele some do bloco "outros" e entra como 22.
    if num_a not in ("22", "13"):
        for m in lista:
            m["votos"].pop(num_a, None)

    total_a = sum(m["alvo"]["pl"] for m in lista)
    total_b = sum(m["alvo"]["pt"] for m in lista)
    with open(saida, "w", encoding="utf-8") as fh:
        json.dump({"municipios": lista, "ano": args.ano}, fh, ensure_ascii=False)

    pa = 100.0 * total_a / (total_a + total_b)
    pb = 100.0 - pa
    print("\nSalvo em %s" % saida)
    print("  municípios: %d" % len(lista))
    print("  2º turno de %d reconstruído:  %s %.2f%%   %s %.2f%%"
          % (args.ano, cfg["nome_a"], pa, cfg["nome_b"], pb))
    print("  resultado oficial do TSE:     %s %.2f%%   %s %.2f%%"
          % (cfg["nome_a"], cfg["oficial_a"], cfg["nome_b"], cfg["oficial_b"]))
    dif = abs(pa - cfg["oficial_a"])
    print("  diferença: %.3f pp  %s" % (dif, "OK" if dif < 0.05 else "VERIFICAR"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
