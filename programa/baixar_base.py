"""
Baixa a BASE do modelo: o resultado final do 1º turno de 2026, município a município.

Essa base é o coração da projeção. Ela responde, para cada um dos ~5.570
municípios: quantos eleitores tem, quantos compareceram, e como votaram em cada
candidato três semanas antes. Como é a MESMA eleição, com os MESMOS eleitores e
as MESMAS seções, ela é uma referência muito melhor do que usar 2022.

Roda uma vez só. Gera base_1t.json (~5 MB). Depois disso o apurador não
precisa mais da internet para nada além dos arquivos do 2º turno.

Uso:  python3 baixar_base.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import tse

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_1t.json")
THREADS = 16
TENTATIVAS = 3


def listar_municipios() -> list:
    doc = tse.baixar_json(tse.url_municipios(tse.ELEICAO_1T))
    municipios = []
    for abr in doc.get("abr", []):
        uf = abr.get("cd", "").lower()
        for mun in abr.get("mu", []):
            municipios.append(
                {"uf": uf, "cd": mun["cd"], "nm": mun.get("nm", ""),
                 "capital": mun.get("c") == "s"}
            )
    return municipios


def baixar_municipio(mun: dict) -> dict | None:
    url = tse.url_resultado_municipio(tse.ELEICAO_1T, mun["uf"], mun["cd"])
    for tentativa in range(TENTATIVAS):
        try:
            doc = tse.baixar_json(url)
        except tse.TSEIndisponivel:
            if tentativa == TENTATIVAS - 1:
                return None
            time.sleep(1.5 * (tentativa + 1))
            continue
        ap = tse.extrair_apuracao(doc)
        return {
            "uf": mun["uf"],
            "cd": mun["cd"],
            "nm": mun["nm"],
            "capital": mun["capital"],
            "regiao": tse.REGIAO.get(mun["uf"], "outros"),
            "eleitorado": ap["eleitorado_total"],
            "comparecimento": ap["comparecimento"],
            "votos_validos": ap["votos_validos"],
            "secoes": ap["secoes_total"],
            "votos": tse.extrair_votos(doc),
        }
    return None


def main() -> int:
    print("Lendo a lista de municípios no TSE...", flush=True)
    try:
        municipios = listar_municipios()
    except tse.TSEIndisponivel as exc:
        print("Não consegui ler a lista de municípios: %s" % exc)
        return 1
    print("%d municípios (+ exterior). Baixando o 1º turno de cada um." % len(municipios))
    print("Isso leva alguns minutos e só precisa ser feito uma vez.\n", flush=True)

    resultados = []
    falhas = []
    feitos = 0
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futuros = {pool.submit(baixar_municipio, m): m for m in municipios}
        for fut in as_completed(futuros):
            mun = futuros[fut]
            try:
                res = fut.result()
            except Exception:
                res = None
            if res is None:
                falhas.append("%s/%s %s" % (mun["uf"], mun["cd"], mun["nm"]))
            else:
                resultados.append(res)
            feitos += 1
            if feitos % 250 == 0 or feitos == len(municipios):
                decorrido = time.time() - inicio
                print("  %5d/%d  (%.0fs, %d falhas)"
                      % (feitos, len(municipios), decorrido, len(falhas)), flush=True)

    if not resultados:
        print("\nNenhum município baixado. Verifique sua conexão.")
        return 1

    total_eleitorado = sum(m["eleitorado"] for m in resultados)
    total_validos = sum(m["votos_validos"] for m in resultados)
    soma = {}
    for m in resultados:
        for n, v in m["votos"].items():
            soma[n] = soma.get(n, 0) + v

    base = {
        "eleicao": tse.ELEICAO_1T,
        "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "municipios": resultados,
        "falhas": falhas,
        "totais": {
            "eleitorado": total_eleitorado,
            "votos_validos": total_validos,
            "votos": soma,
        },
    }
    with open(SAIDA, "w", encoding="utf-8") as fh:
        json.dump(base, fh, ensure_ascii=False)

    print("\nBase salva em %s" % SAIDA)
    print("  municípios: %d   falhas: %d" % (len(resultados), len(falhas)))
    print("  eleitorado: %s   votos válidos: %s"
          % (f"{total_eleitorado:,}".replace(",", "."),
             f"{total_validos:,}".replace(",", ".")))

    # Conferência contra o total nacional publicado pelo TSE.
    try:
        br = tse.baixar_json(tse.url_resultado_br(tse.ELEICAO_1T))
        oficial = tse.extrair_votos(br)
        print("\n  conferência (soma dos municípios vs. total nacional do TSE):")
        for n in (tse.NUM_PL, tse.NUM_PT):
            meu, dele = soma.get(n, 0), oficial.get(n, 0)
            dif = meu - dele
            print("    nº %s: %12s vs %12s   diferença %+d"
                  % (n, f"{meu:,}".replace(",", "."),
                     f"{dele:,}".replace(",", "."), dif))
    except tse.TSEIndisponivel:
        pass

    if falhas:
        print("\n  municípios que falharam (rode de novo para completar):")
        for f in falhas[:20]:
            print("    " + f)
        if len(falhas) > 20:
            print("    ... e mais %d" % (len(falhas) - 20))
    return 0


if __name__ == "__main__":
    sys.exit(main())
