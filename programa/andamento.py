"""
Leitura do andamento da apuração: quanto de cada município já foi totalizado.

O arquivo de andamento (`-ab.json`) de cada UF traz, para TODOS os municípios
daquela UF, o eleitorado já totalizado e o horário em que cada município
concluiu. Dois usos:

  ao vivo   -> quanto cada município já apurou agora
  histórico -> em que ordem a apuração chegou (usado no backtest)

São 27 arquivos por leitura, o que mantém o programa leve mesmo atualizando de
minuto em minuto.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import tse

AQUI = os.path.dirname(os.path.abspath(__file__))
ORDEM_1T = os.path.join(AQUI, "ordem_1t_2026.json")


def _ler_uf(eleicao: int, uf: str) -> tuple:
    try:
        doc = tse.baixar_json(tse.url_andamento_uf(eleicao, uf))
    except tse.TSEIndisponivel:
        return uf, None
    municipios = {}
    for abr in doc.get("abr", []):
        if abr.get("tpabr") != "mun":
            continue
        cd = abr.get("cdabr")
        e = abr.get("e", {}) or {}
        s = abr.get("s", {}) or {}
        total = tse._num(e.get("te", 0))
        apurado = tse._num(e.get("est", 0))
        municipios["%s/%s" % (uf, cd)] = {
            "fracao": (apurado / total) if total > 0 else 0.0,
            "eleitorado": int(total),
            "eleitorado_apurado": int(apurado),
            "secoes": int(tse._num(s.get("ts", 0))),
            "secoes_apuradas": int(tse._num(s.get("st", 0))),
            "concluido": abr.get("and") == "f",
            "data": abr.get("dt", ""),
            "hora": abr.get("ht", ""),
        }
    return uf, municipios


def ler_tudo(eleicao: int, ufs: list | None = None, threads: int = 12) -> dict:
    ufs = ufs or tse.UFS
    saida = {}
    indisponiveis = []
    with ThreadPoolExecutor(max_workers=threads) as pool:
        for uf, muns in pool.map(lambda u: _ler_uf(eleicao, u), ufs):
            if muns is None:
                indisponiveis.append(uf)
            else:
                saida.update(muns)
    return {"municipios": saida, "indisponiveis": indisponiveis}


def fracoes(eleicao: int) -> dict:
    """Só o que o modelo precisa: {"uf/cd": fracao}."""
    dados = ler_tudo(eleicao)
    return {k: v["fracao"] for k, v in dados["municipios"].items()}


# ----------------------------------------------------------------------
def salvar_ordem_1t() -> dict:
    """
    Congela a ordem real de chegada do 1º turno de 2026.

    É a ordem de apuração mais fiel que existe para o backtest: mesma
    logística, mesmas zonas eleitorais, mesmo país, três semanas antes.
    """
    dados = ler_tudo(tse.ELEICAO_1T)
    ordem = []
    for chave, m in dados["municipios"].items():
        if not m["data"] or not m["hora"]:
            continue
        dia, mes, ano = m["data"].split("/")
        ordem.append({
            "chave": chave,
            "instante": "%s-%s-%s %s" % (ano, mes, dia, m["hora"]),
            "eleitorado": m["eleitorado"],
            "secoes": m["secoes"],
        })
    ordem.sort(key=lambda x: x["instante"])
    with open(ORDEM_1T, "w", encoding="utf-8") as fh:
        json.dump({"ordem": ordem, "indisponiveis": dados["indisponiveis"]},
                  fh, ensure_ascii=False)
    return {"municipios": len(ordem), "indisponiveis": dados["indisponiveis"]}


def carregar_ordem_1t() -> list:
    with open(ORDEM_1T, encoding="utf-8") as fh:
        return json.load(fh)["ordem"]


if __name__ == "__main__":
    print("Lendo o andamento do 1º turno para congelar a ordem de chegada...")
    r = salvar_ordem_1t()
    print("  %d municípios com horário de totalização" % r["municipios"])
    if r["indisponiveis"]:
        print("  UFs indisponíveis: %s" % ", ".join(r["indisponiveis"]))
    ordem = carregar_ordem_1t()
    print("  primeiro a fechar: %s às %s" % (ordem[0]["chave"], ordem[0]["instante"]))
    print("  último a fechar:   %s às %s" % (ordem[-1]["chave"], ordem[-1]["instante"]))
