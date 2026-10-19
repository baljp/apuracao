"""
Acesso aos arquivos oficiais de divulgação de resultados do TSE (eleições 2026).

Nada aqui é "API privada": são os mesmos arquivos JSON públicos que o site
resultados.tse.jus.br consome, documentados pelo TSE na página
"Informações técnicas sobre a divulgação de resultados".

Estrutura das URLs (confirmada contra o ambiente oficial em 2026):

  base   = https://resultados.tse.jus.br/oficial
  ciclo  = ele2026
  eleição federal 1º turno = 6257   (pleito 3220, 04/10/2026)
  eleição federal 2º turno = 6258   (pleito 3221, 25/10/2026)
  cargo Presidente         = c0001

  resultado  <uf>/<uf>-c0001-e<NNNNNN>-u.json
  município  <uf>/<uf><cdmun>-c0001-e<NNNNNN>-u.json
  andamento  <uf>/<uf>-e<NNNNNN>-ab.json      (traz TODOS os municípios da UF)
  municípios config/mun-e<NNNNNN>-cm.json
"""

from __future__ import annotations

import gzip
import io
import json
import urllib.error
import urllib.request

BASE = "https://resultados.tse.jus.br/oficial"
CICLO = "ele2026"

ELEICAO_1T = 6257
ELEICAO_2T = 6258

CARGO_PRESIDENTE = "c0001"

# Os dois candidatos do 2º turno.
NUM_PL = "22"   # Flávio Bolsonaro
NUM_PT = "13"   # Lula

UFS = [
    "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms",
    "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc",
    "se", "sp", "to", "zz",  # zz = exterior
]

REGIAO = {
    "ac": "norte", "am": "norte", "ap": "norte", "pa": "norte", "ro": "norte",
    "rr": "norte", "to": "norte",
    "al": "nordeste", "ba": "nordeste", "ce": "nordeste", "ma": "nordeste",
    "pb": "nordeste", "pe": "nordeste", "pi": "nordeste", "rn": "nordeste",
    "se": "nordeste",
    "df": "centro-oeste", "go": "centro-oeste", "ms": "centro-oeste",
    "mt": "centro-oeste",
    "es": "sudeste", "mg": "sudeste", "rj": "sudeste", "sp": "sudeste",
    "pr": "sul", "rs": "sul", "sc": "sul",
    "zz": "exterior",
}

UA = "apurador-local/1.0 (uso pessoal; arquivos publicos de divulgacao do TSE)"


class TSEIndisponivel(Exception):
    """O arquivo pedido não existe ainda ou o TSE não respondeu."""


def _e(cod: int) -> str:
    """6257 -> 'e006257'."""
    return "e%06d" % cod


def baixar_json(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                dados = gzip.GzipFile(fileobj=io.BytesIO(dados)).read()
    except urllib.error.HTTPError as exc:
        raise TSEIndisponivel("%s -> HTTP %s" % (url, exc.code)) from exc
    except Exception as exc:  # timeout, DNS, conexão
        raise TSEIndisponivel("%s -> %s" % (url, exc)) from exc
    try:
        return json.loads(dados)
    except ValueError as exc:
        raise TSEIndisponivel("%s -> resposta não é JSON" % url) from exc


def url_resultado_uf(eleicao: int, uf: str) -> str:
    return "%s/%s/%d/dados/%s/%s-%s-%s-u.json" % (
        BASE, CICLO, eleicao, uf, uf, CARGO_PRESIDENTE, _e(eleicao)
    )


def url_resultado_br(eleicao: int) -> str:
    return url_resultado_uf(eleicao, "br")


def url_resultado_municipio(eleicao: int, uf: str, cdmun: str) -> str:
    return "%s/%s/%d/dados/%s/%s%s-%s-%s-u.json" % (
        BASE, CICLO, eleicao, uf, uf, cdmun, CARGO_PRESIDENTE, _e(eleicao)
    )


def url_andamento_uf(eleicao: int, uf: str) -> str:
    return "%s/%s/%d/dados/%s/%s-%s-ab.json" % (
        BASE, CICLO, eleicao, uf, uf, _e(eleicao)
    )


def url_municipios(eleicao: int) -> str:
    return "%s/%s/%d/config/mun-%s-cm.json" % (BASE, CICLO, eleicao, _e(eleicao))


def _num(txt) -> float:
    """'47,03' -> 47.03 ; '56104503' -> 56104503.0 ; '' -> 0.0"""
    if txt in (None, ""):
        return 0.0
    if isinstance(txt, (int, float)):
        return float(txt)
    return float(str(txt).replace(".", "").replace(",", ".")) if "," in str(txt) \
        else float(str(txt))


def extrair_votos(doc: dict) -> dict:
    """Votos por número de candidato a partir de um arquivo de resultado."""
    votos = {}
    for cargo in doc.get("carg", []):
        for agr in cargo.get("agr", []):
            for par in agr.get("par", []):
                for cand in par.get("cand", []):
                    n = cand.get("n")
                    if n:
                        votos[n] = votos.get(n, 0) + int(_num(cand.get("vap", 0)))
    return votos


def extrair_apuracao(doc: dict) -> dict:
    """Seções, eleitorado e comparecimento já totalizados."""
    s = doc.get("s", {}) or {}
    e = doc.get("e", {}) or {}
    v = doc.get("v", {}) or {}
    return {
        "secoes_total": int(_num(s.get("ts", 0))),
        "secoes_apuradas": int(_num(s.get("st", 0))),
        "eleitorado_total": int(_num(e.get("te", 0))),
        "eleitorado_apurado": int(_num(e.get("est", 0))),
        "comparecimento": int(_num(e.get("c", 0))),
        "abstencao": int(_num(e.get("a", 0))),
        "votos_validos": int(_num(v.get("vv", 0))),
        "brancos": int(_num(v.get("vb", 0))),
        "nulos": int(_num(v.get("tvn", 0))),
        "finalizado": doc.get("and") == "f",
        "data": doc.get("dt", ""),
        "hora": doc.get("ht", ""),
    }
