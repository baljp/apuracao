"""
Apurador — projeção ao vivo do 2º turno presidencial a partir dos arquivos
oficiais do TSE.

Como rodar:

    python3 apurador.py

Abra http://localhost:8600 no navegador. O programa busca os dados do TSE a
cada 30 segundos, roda o modelo e atualiza o painel sozinho. Pode deixar aberto
a noite toda.

Opções:
    --porta 8600        porta do painel
    --intervalo 30      segundos entre as leituras do TSE
    --turno 1           acompanha o 1º turno (útil para testar fora do dia)
    --sem-navegador     não abre o navegador automaticamente
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import andamento
import modelo
import tse

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(AQUI, "base_1t.json")
PAINEL = os.path.join(AQUI, "painel.html")

estado = {
    "pronto": False,
    "erro": None,
    "atualizado_em": None,
    "resultado": None,
    "historico": [],
    "nomes": {"pl": "22", "pt": "13"},
    "turno": 2,
}
trava = threading.Lock()


# ---------------------------------------------------------------- coleta
def ler_uf(eleicao: int, uf: str):
    try:
        doc = tse.baixar_json(tse.url_resultado_uf(eleicao, uf))
    except tse.TSEIndisponivel:
        return uf, None, None
    votos = tse.extrair_votos(doc)
    nomes = {}
    for cargo in doc.get("carg", []):
        for agr in cargo.get("agr", []):
            for par in agr.get("par", []):
                for cand in par.get("cand", []):
                    if cand.get("n") in (tse.NUM_PL, tse.NUM_PT):
                        nomes[cand["n"]] = cand.get("nmu", cand["n"]).title()
    return uf, {"pl": votos.get(tse.NUM_PL, 0),
                "pt": votos.get(tse.NUM_PT, 0)}, nomes


def coletar(eleicao: int) -> tuple:
    """Lê os 27 resultados por UF e os 27 andamentos, em paralelo."""
    observado = {}
    nomes = {}
    indisponiveis = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for uf, votos, nms in pool.map(lambda u: ler_uf(eleicao, u), tse.UFS):
            if votos is None:
                indisponiveis.append(uf)
            else:
                observado[uf] = votos
                nomes.update(nms or {})
    fracoes = andamento.fracoes(eleicao)
    return observado, fracoes, nomes, indisponiveis


def ciclo(mdl, eleicao: int, intervalo: int):
    while True:
        try:
            observado, fracoes, nomes, indisp = coletar(eleicao)
            r = mdl.projetar(fracoes, observado, n_bootstrap=300)
            with trava:
                estado["resultado"] = r
                estado["atualizado_em"] = time.strftime("%H:%M:%S")
                estado["indisponiveis"] = indisp
                estado["pronto"] = True
                estado["erro"] = None
                if nomes:
                    estado["nomes"] = {"pl": nomes.get(tse.NUM_PL, "22"),
                                       "pt": nomes.get(tse.NUM_PT, "13")}
                hist = estado["historico"]
                if r["pct_apurado"] > 0 and (
                        not hist or r["pct_apurado"] > hist[-1]["pct"] + 0.05):
                    hist.append({"pct": r["pct_apurado"],
                                 "proj": r["projecao_pl"],
                                 "bruto": r["bruto_pl"],
                                 "hora": estado["atualizado_em"]})
            pct = r["pct_apurado"]
            if pct <= 0:
                print("  apuração ainda não começou (%s)" % time.strftime("%H:%M:%S"),
                      flush=True)
            else:
                print("  %5.2f%% apurado   projeção: %s %.2f%% x %.2f%% %s   (±%.2f)"
                      % (pct, estado["nomes"]["pl"], r["projecao_pl"],
                         r["projecao_pt"], estado["nomes"]["pt"],
                         (r["faixa_pl"][1] - r["faixa_pl"][0]) / 2), flush=True)
        except Exception as exc:  # rede caiu, TSE fora do ar, etc.
            with trava:
                estado["erro"] = str(exc)
            print("  falha ao atualizar: %s" % exc, flush=True)
        time.sleep(intervalo)


# ---------------------------------------------------------------- painel
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # silencia o log de requisições

    def do_GET(self):
        if self.path.startswith("/api"):
            with trava:
                corpo = json.dumps(estado, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        try:
            with open(PAINEL, "rb") as fh:
                corpo = fh.read()
        except OSError:
            corpo = b"<h1>painel.html nao encontrado</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


def main() -> int:
    p = argparse.ArgumentParser(description="Projeção ao vivo da apuração do TSE")
    p.add_argument("--porta", type=int, default=8600)
    p.add_argument("--intervalo", type=int, default=30)
    p.add_argument("--turno", type=int, default=2, choices=(1, 2))
    p.add_argument("--sem-navegador", action="store_true")
    args = p.parse_args()

    if not os.path.exists(BASE):
        print("Falta a base do 1º turno. Rode antes:\n    python3 baixar_base.py")
        return 1

    print("Carregando a base do 1º turno...")
    with open(BASE, encoding="utf-8") as fh:
        base = json.load(fh)
    mdl = modelo.Modelo(base)
    print("  %d municípios, %.1f milhões de eleitores\n"
          % (len(mdl.municipios), mdl.eleitorado_total / 1e6))

    eleicao = tse.ELEICAO_2T if args.turno == 2 else tse.ELEICAO_1T
    estado["turno"] = args.turno

    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url = "http://localhost:%d" % args.porta
    print("Painel em %s" % url)
    print("Lendo o TSE a cada %d segundos. Ctrl+C para parar.\n" % args.intervalo)
    if not args.sem_navegador:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        ciclo(mdl, eleicao, args.intervalo)
    except KeyboardInterrupt:
        print("\nEncerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
