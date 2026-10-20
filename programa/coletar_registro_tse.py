"""
Gera o `registro-tse.json`: o registro oficial das pesquisas do 2º turno.

POR QUE ISTO EXISTE
Os percentuais das pesquisas vêm da Wikipédia, que qualquer um edita. O TSE
não publica percentual nenhum — mas publica o REGISTRO de toda pesquisa
divulgada: empresa, protocolo, contratante, tamanho da amostra, datas de
campo e de divulgação. É a única fonte oficial que existe sobre o assunto, e
serve para responder a pergunta que importa: esta pesquisa que está na
tabela existe de verdade?

A coluna TSE da página é isso. Sem este arquivo ela fica vazia — e a página
ficou meses prometendo no texto uma validação que não estava acontecendo,
porque `cruzarComTSE` trata a ausência do arquivo em silêncio. Se este
script deixar de rodar, o sintoma é esse: coluna vazia, nenhum erro.

DE ONDE VEM
Dados abertos do TSE, pacote "Pesquisas Eleitorais - 2026". O TSE regera os
arquivos todo dia — os que este script baixa trazem a hora de geração dentro
do próprio zip, e ela é conferida abaixo. Isso importa porque pesquisa de
véspera é registrada em cima da hora: na eleição de 2026, pesquisas com
divulgação marcada para 24/10 já constavam do registro no dia 19.

O sistema de consulta por formulário (pesqele-divulgacao.tse.jus.br) recusa
acesso vindo de datacenter. Os dados abertos, não — por isso este caminho.

SOBRE OS NOMES
A Wikipédia escreve "Datafolha", "Quaest/Genial", "Nexus/BTG". O TSE
registra a razão social: "DATAFOLHA INSTITUTO DE PESQUISAS LTDA.". O
cruzamento em pesquisas.js compara os dois normalizados, aceitando um conter
o outro. Então este arquivo traz, para cada registro, TODAS as formas do
nome que o TSE fornece — razão social e nome fantasia —, cada uma como uma
entrada. Nome fantasia vem "#NULO#" com frequência (inclusive no Datafolha),
e é por isso que as duas formas são necessárias.

Uso:  python3 programa/coletar_registro_tse.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import urllib.request
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA = os.path.join(RAIZ, "registro-tse.json")

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral"
URL_PESQUISAS = CDN + "/pesquisa_eleitoral_2026.zip"
URL_CONTRATANTES = CDN + "/pesquisa_contratante_2026.zip"

ARQ_NACIONAL = "pesquisa_eleitoral_2026_BRASIL.csv"
ARQ_CONTRATANTES = "pesquisa_contratante_2026_BRASIL.csv"

# Só presidência, e só o que tem campo dentro da janela do 2º turno. O 1º
# turno foi em 4/10; o corte em 1/10 pega a virada com folga.
CARGO = "Presidente"
DESDE = "2026-10-01"

NULO = "#NULO#"


def baixar(url: str) -> zipfile.ZipFile:
    with urllib.request.urlopen(url, timeout=180) as resp:
        return zipfile.ZipFile(io.BytesIO(resp.read()))


def ler_csv(z: zipfile.ZipFile, nome: str) -> list[dict]:
    with z.open(nome) as fh:
        return list(csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"),
                                   delimiter=";"))


def inteiro(txt: str) -> int | None:
    txt = (txt or "").strip()
    return int(txt) if txt.isdigit() else None


def main() -> int:
    try:
        zp = baixar(URL_PESQUISAS)
        zc = baixar(URL_CONTRATANTES)
    except Exception as erro:
        print("não consegui baixar os dados abertos do TSE: %s" % erro)
        return 1

    # A hora de geração vem dentro do zip. Arquivo velho aqui significa
    # pesquisa nova faltando na coluna TSE, e isso tem que aparecer.
    info = zp.getinfo(ARQ_NACIONAL)
    gerado = "%04d-%02d-%02d %02d:%02d" % info.date_time[:5]

    linhas = ler_csv(zp, ARQ_NACIONAL)
    contratantes: dict[str, list[str]] = {}
    for c in ler_csv(zc, ARQ_CONTRATANTES):
        nome = (c.get("NM_CONTRATANTE") or "").strip()
        if nome and nome != NULO:
            contratantes.setdefault(c["NR_PROTOCOLO_REGISTRO"], []).append(nome)

    registros = []
    protocolos = set()
    for x in linhas:
        if x.get("DS_CARGO") != CARGO:
            continue
        if (x.get("DT_FIM_PESQUISA") or "") < DESDE:
            continue
        protocolo = x["NR_PROTOCOLO_REGISTRO"]
        protocolos.add(protocolo)
        amostra = inteiro(x.get("QT_ENTREVISTADO"))
        quem = contratantes.get(protocolo, [])
        comum = {
            "protocolo": protocolo,
            "amostra": amostra,
            "contratante": ", ".join(quem[:3]) if quem else None,
            "inicio": (x.get("DT_INICIO_PESQUISA") or "")[:10],
            "fim": (x.get("DT_FIM_PESQUISA") or "")[:10],
            "divulgacao": (x.get("DT_DIVULGACAO") or "")[:10],
        }
        # Uma entrada por forma do nome: a página cruza por nome, e o nome
        # que a Wikipédia usa pode ser qualquer uma das duas.
        nomes = []
        for chave in ("NM_EMPRESA", "NM_EMPRESA_FANTASIA"):
            v = (x.get(chave) or "").strip()
            if v and v != NULO and v not in nomes:
                nomes.append(v)
        for nome in nomes:
            registros.append({"empresa": nome, **comum})

    if not registros:
        print("nenhum registro de presidente a partir de %s — não gravo nada,"
              " porque arquivo vazio apagaria a coluna TSE sem avisar" % DESDE)
        return 1

    saida = {
        "fonte": "dados abertos do TSE, pacote Pesquisas Eleitorais 2026",
        "url": URL_PESQUISAS,
        "gerado_pelo_tse_em": gerado,
        "cargo": CARGO,
        "campo_desde": DESDE,
        "pesquisas": registros,
    }
    with open(SAIDA, "w", encoding="utf-8") as fh:
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"))

    print("registro-tse.json gravado")
    print("  %d pesquisas de presidente registradas desde %s" % (len(protocolos), DESDE))
    print("  %d entradas (razão social + nome fantasia)" % len(registros))
    print("  arquivo do TSE gerado em %s" % gerado)
    print("  %.0f KB" % (os.path.getsize(SAIDA) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
