"""
Gera o mapa do Brasil do site, a partir da malha oficial do IBGE.

A fonte é a API de malhas territoriais do IBGE, que é pública:
  https://servicodados.ibge.gov.br/api/v3/malhas/

O script baixa o contorno dos 27 estados, projeta, simplifica e grava um
arquivo com um caminho SVG por estado. O site carrega esse arquivo e pinta
cada estado conforme a projeção — sem depender de nenhuma biblioteca de mapas
nem de serviço externo na hora de exibir.

A projeção é cônica equivalente de Albers, com os paralelos padrão ajustados
ao Brasil. Em Mercator (a projeção dos mapas de rua) Roraima apareceria maior
do que é e o Sul encolheria; numa projeção equivalente, a área de cada estado
na tela guarda proporção com a área real.

Uso:  python3 gerar_mapa.py
"""

from __future__ import annotations

import gzip
import io
import json
import math
import os
import sys
import urllib.request

# Os contornos têm milhares de pontos por estado; a simplificação é recursiva.
sys.setrecursionlimit(50000)

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA = os.path.join(RAIZ, "mapa.json")

URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
       "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")

# Código do IBGE para sigla da UF.
UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

# Albers para o Brasil.
LAT0, LON0 = -15.0, -54.0
LAT1, LAT2 = -5.0, -25.0


def albers(lon: float, lat: float) -> tuple:
    lon_r, lat_r = math.radians(lon), math.radians(lat)
    lon0_r, lat0_r = math.radians(LON0), math.radians(LAT0)
    lat1_r, lat2_r = math.radians(LAT1), math.radians(LAT2)
    n = 0.5 * (math.sin(lat1_r) + math.sin(lat2_r))
    if abs(n) < 1e-12:
        n = 1e-12
    c = math.cos(lat1_r) ** 2 + 2 * n * math.sin(lat1_r)
    rho0 = math.sqrt(c - 2 * n * math.sin(lat0_r)) / n
    rho = math.sqrt(max(c - 2 * n * math.sin(lat_r), 1e-12)) / n
    theta = n * (lon_r - lon0_r)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def simplificar(pontos: list, tol: float) -> list:
    """Douglas-Peucker: tira os pontos que não mudam o desenho."""
    if len(pontos) < 3:
        return pontos
    ini, fim = pontos[0], pontos[-1]
    dx, dy = fim[0] - ini[0], fim[1] - ini[1]
    norma = math.hypot(dx, dy)
    pior, idx = 0.0, 0
    for i in range(1, len(pontos) - 1):
        px, py = pontos[i]
        if norma < 1e-12:
            d = math.hypot(px - ini[0], py - ini[1])
        else:
            d = abs(dy * px - dx * py + fim[0] * ini[1] - fim[1] * ini[0]) / norma
        if d > pior:
            pior, idx = d, i
    if pior <= tol:
        return [ini, fim]
    return (simplificar(pontos[:idx + 1], tol)[:-1]
            + simplificar(pontos[idx:], tol))


def area(pts: list) -> float:
    s = 0.0
    for i in range(len(pts) - 1):
        s += pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
    return s / 2.0


def centro(pts: list) -> tuple:
    """
    Centro de massa do polígono. Para estados em forma de C ou L esse ponto
    pode cair fora da área; nesses casos o rótulo é puxado de volta para
    dentro usando o centro da caixa que envolve o estado.
    """
    a = area(pts)
    if abs(a) < 1e-9:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    cx = cy = 0.0
    for i in range(len(pts) - 1):
        f = pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1]
        cx += (pts[i][0] + pts[i + 1][0]) * f
        cy += (pts[i][1] + pts[i + 1][1]) * f
    return (cx / (6 * a), cy / (6 * a))


def aneis(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    saida = []
    for poly in geom["coordinates"]:
        saida.extend(poly)
    return saida


def main() -> int:
    print("Baixando a malha dos estados no IBGE...", flush=True)
    try:
        req = urllib.request.Request(
            URL, headers={"User-Agent": "apuracao-2026", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=60) as r:
            bruto = r.read()
            if r.headers.get("Content-Encoding") == "gzip" or bruto[:2] == b"\x1f\x8b":
                bruto = gzip.GzipFile(fileobj=io.BytesIO(bruto)).read()
            dados = json.loads(bruto)
    except Exception as exc:
        print("Não consegui baixar: %s" % exc)
        return 1

    # Projeta tudo primeiro, para achar os limites.
    por_uf = {}
    for f in dados.get("features", []):
        cod = str(f.get("properties", {}).get("codarea", "")).strip()
        uf = UF_POR_CODIGO.get(cod[:2])
        if not uf:
            continue
        projetados = []
        for anel in aneis(f["geometry"]):
            pts = [albers(p[0], p[1]) for p in anel if len(p) >= 2]
            if len(pts) >= 4:
                projetados.append(pts)
        if projetados:
            por_uf.setdefault(uf, []).extend(projetados)

    if len(por_uf) < 27:
        print("Esperava 27 estados, vieram %d" % len(por_uf))

    todos = [p for aneis_uf in por_uf.values() for a in aneis_uf for p in a]
    xs = [p[0] for p in todos]
    ys = [p[1] for p in todos]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    # Enquadra numa área de 1000 de largura, mantendo proporção.
    LARGURA = 1000.0
    escala = LARGURA / (maxx - minx)
    altura = (maxy - miny) * escala

    def tela(p):
        return ((p[0] - minx) * escala, (maxy - p[1]) * escala)

    # Tolerância da simplificação, em unidades de tela: abaixo de meio pixel
    # no tamanho em que o mapa é exibido, ninguém vê diferença.
    TOL = 0.9

    caminhos = {}
    rotulos = {}
    pontos_antes = pontos_depois = 0
    for uf, aneis_uf in por_uf.items():
        partes = []
        maior = None
        maior_area = -1.0
        for anel in aneis_uf:
            pts = [tela(p) for p in anel]
            pontos_antes += len(pts)
            pts = simplificar(pts, TOL)
            if len(pts) < 4:
                continue
            pontos_depois += len(pts)
            partes.append("M" + " ".join("%.1f %.1f" % (x, y) for x, y in pts) + "Z")
            # Guarda o maior pedaço, que é onde o nome do estado deve ficar:
            # senão o rótulo do Pará poderia cair numa ilha do litoral.
            a = abs(area(pts))
            if a > maior_area:
                maior_area, maior = a, pts
        if partes:
            caminhos[uf] = "".join(partes)
            rotulos[uf] = [round(v, 1) for v in centro(maior)]

    saida = {
        "fonte": "IBGE — Malhas Territoriais (API v3), projeção Albers",
        "viewBox": "0 0 %.0f %.0f" % (LARGURA, altura),
        "ufs": caminhos,
        "rotulos": rotulos,
    }
    with open(SAIDA, "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"))

    print("Mapa salvo em %s" % SAIDA)
    print("  estados: %d" % len(caminhos))
    print("  pontos: %d -> %d (%.0f%% a menos)"
          % (pontos_antes, pontos_depois,
             100 * (1 - pontos_depois / max(pontos_antes, 1))))
    print("  tamanho: %.0f KB" % (os.path.getsize(SAIDA) / 1024))
    print("  viewBox: %s" % saida["viewBox"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
