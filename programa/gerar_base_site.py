"""
Gera a base enxuta que o site carrega no navegador.

base_1t.json tem 1,7 MB porque guarda tudo. O site só precisa de cinco números
por município, então aqui eles viram colunas paralelas de inteiros — fica em
torno de 250 KB, que carrega num piscar mesmo em conexão de celular.

Formato de saída (site/base.json):

    {
      "gerado_em": "...",
      "nomes": {"pl": "...", "pt": "..."},
      "ufs":   ["ac","ac",...]      uf de cada município
      "cds":   ["01120",...]        código do município no TSE
      "nms":   ["ACRELÂNDIA",...]   nome
      "ele":   [6336,...]           eleitorado
      "pl":    [1234,...]           votos do finalista do PL no 1º turno
      "pt":    [987,...]            votos do finalista do PT no 1º turno
      "out":   [210,...]            votos dos candidatos eliminados
    }

Uso:  python3 gerar_base_site.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import tse

AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(AQUI, "base_1t.json")
SAIDA_DIR = os.path.join(AQUI, "site")
SAIDA = os.path.join(SAIDA_DIR, "base.json")


def main() -> int:
    if not os.path.exists(ENTRADA):
        print("Falta base_1t.json — rode antes: python3 baixar_base.py")
        return 1

    with open(ENTRADA, encoding="utf-8") as fh:
        base = json.load(fh)

    ufs, cds, nms, ele, pl, pt, out = [], [], [], [], [], [], []
    for m in base["municipios"]:
        votos = m.get("votos", {}) or {}
        v_pl = int(votos.get(tse.NUM_PL, 0))
        v_pt = int(votos.get(tse.NUM_PT, 0))
        if v_pl + v_pt <= 0 or m.get("eleitorado", 0) <= 0:
            continue
        outros = sum(int(v) for n, v in votos.items()
                     if n not in (tse.NUM_PL, tse.NUM_PT))
        ufs.append(m["uf"])
        cds.append(m["cd"])
        nms.append(m["nm"])
        ele.append(int(m["eleitorado"]))
        pl.append(v_pl)
        pt.append(v_pt)
        out.append(outros)

    # Nomes dos finalistas, lidos do próprio TSE.
    nomes = {"pl": "22", "pt": "13"}
    try:
        doc = tse.baixar_json(tse.url_resultado_br(tse.ELEICAO_2T))
        for cargo in doc.get("carg", []):
            for agr in cargo.get("agr", []):
                for par in agr.get("par", []):
                    for cand in par.get("cand", []):
                        if cand.get("n") == tse.NUM_PL:
                            nomes["pl"] = cand.get("nmu", "22").title()
                        elif cand.get("n") == tse.NUM_PT:
                            nomes["pt"] = cand.get("nmu", "13").title()
    except tse.TSEIndisponivel:
        pass

    os.makedirs(SAIDA_DIR, exist_ok=True)
    saida = {
        "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "nomes": nomes,
        "ufs": ufs, "cds": cds, "nms": nms,
        "ele": ele, "pl": pl, "pt": pt, "out": out,
    }
    with open(SAIDA, "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"))

    tam = os.path.getsize(SAIDA)
    total_pl, total_pt = sum(pl), sum(pt)
    print("Base do site gerada: %s" % SAIDA)
    print("  municípios: %d" % len(ufs))
    print("  tamanho: %.0f KB" % (tam / 1024))
    print("  finalistas: %s x %s" % (nomes["pl"], nomes["pt"]))
    print("  1º turno entre os dois: %.2f%% x %.2f%%"
          % (100.0 * total_pl / (total_pl + total_pt),
             100.0 * total_pt / (total_pl + total_pt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
