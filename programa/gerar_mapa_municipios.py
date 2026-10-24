"""
Gera o mapa-mun.json: os 5,6 mil municípios do Brasil para o mapa do site.

Passos:
  1. baixa a malha municipal (IBGE, via github.com/tbrugz/geodata-br) e a
     tabela do TSE que liga o código do IBGE ao código do TSE de cada cidade
     (config/mun-e006257-cm.json, campo "cdi");
  2. corrige polígonos em que o contorno de verdade veio marcado como buraco;
  3. projeta em Albers (a mesma do mapa dos estados) e simplifica com o
     mapshaper (npx mapshaper), guardando a topologia — a divisa entre duas
     cidades é desenhada uma vez só;
  4. grava arcos com coordenadas inteiras em diferenças, o que deixa o
     arquivo em ~700 KB (~250 KB comprimido pelo servidor).

Uso:  python3 programa/gerar_mapa_municipios.py   (precisa de node/npx)
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CM = "https://resultados.tse.jus.br/oficial/ele2026/6257/config/mun-e006257-cm.json"
GEO = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-%s-mun.json"
UFS_IBGE = "11 12 13 14 15 16 17 21 22 23 24 25 26 27 28 29 31 32 33 35 41 42 43 50 51 52 53".split()
PROJ = "+proj=aea +lat_1=-5 +lat_2=-25 +lat_0=-15 +lon_0=-54 +datum=WGS84"


def baixar(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "apuracao"}), timeout=90) as r:
        return json.loads(r.read())


def area(r):
    return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2)


def main() -> int:
    cm = baixar(CM)
    ibge2tse = {m["cdi"]: (a["cd"], m["cd"]) for a in cm["abr"] for m in a["mu"]}
    feats = []
    for c in UFS_IBGE:
        for ft in baixar(GEO % c)["features"]:
            t = ibge2tse.get(ft["properties"]["id"])
            if not t:
                continue
            g = ft["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            novo = []
            for p in polys:
                if len(p) > 1 and area(p[0]) < max(area(r) for r in p[1:]):
                    novo += [[r] for r in sorted(p, key=area, reverse=True)]
                else:
                    novo.append(p)
            feats.append({"type": "Feature", "properties": {"k": t[0] + "/" + t[1], "uf": t[0]},
                          "geometry": {"type": "MultiPolygon", "coordinates": novo}})
    tmp = tempfile.mkdtemp()
    ent, sai = os.path.join(tmp, "mun.json"), os.path.join(tmp, "mun.topo.json")
    json.dump({"type": "FeatureCollection", "features": feats}, open(ent, "w"))
    subprocess.check_call(["npx", "-y", "mapshaper@0.6", ent, "-proj", *PROJ.split(),
                           "-simplify", "5%", "keep-shapes", "planar",
                           "-o", "format=topojson", "no-quantization", sai, "force"])
    subprocess.check_call([sys.executable, os.path.join(AQUI, "_topo_para_site.py"), sai,
                           os.path.join(RAIZ, "mapa-mun.json")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
