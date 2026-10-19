"""
Gera o `apuracao.html`: um arquivo único, sem nenhuma dependência externa.

Pega o site inteiro — página, modelo, leitura do TSE e a base dos 5.716
municípios — e costura tudo dentro de um HTML só. O arquivo pode ser salvo no
celular, mandado por WhatsApp ou guardado num pendrive: abre direto, sem
servidor e sem internet para carregar (só precisa de rede para buscar os dados
do TSE, que é o ponto).

Isso funciona porque o TSE libera CORS inclusive para origem nula, que é o caso
de um arquivo aberto do próprio aparelho.

Uso:  python3 gerar_html_unico.py
"""

from __future__ import annotations

import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA = os.path.join(RAIZ, "apuracao.html")


def ler(nome: str) -> str:
    with open(os.path.join(RAIZ, nome), encoding="utf-8") as fh:
        return fh.read()


def tirar_exports(js: str) -> str:
    """Transforma um módulo ES em código solto, para caber num <script> só."""
    js = re.sub(r"^\s*import\s+.*?;\s*$", "", js, flags=re.MULTILINE | re.DOTALL)
    js = re.sub(r"^export\s+", "", js, flags=re.MULTILINE)
    return js


def main() -> int:
    for nome in ("index.html", "modelo.js", "tse.js", "base.json"):
        if not os.path.exists(os.path.join(RAIZ, nome)):
            print("Falta %s — rode antes gerar_base_site.py" % nome)
            return 1

    html = ler("index.html")
    modelo = tirar_exports(ler("modelo.js"))
    tsejs = tirar_exports(ler("tse.js"))
    base = json.loads(ler("base.json"))

    # O módulo tse.js expõe suas funções com nomes curtos; dentro do arquivo
    # único elas viram globais, então o código da página passa a chamá-las
    # por um objeto `tse` montado aqui.
    ponte = """
const tse = { lerTudo, lerResultados, lerAndamento, ELEICAO_1T, ELEICAO_2T, UFS };
const BASE_EMBUTIDA = __BASE__;
"""

    script_pagina = re.search(
        r'<script type="module">(.*?)</script>', html, re.DOTALL
    )
    if not script_pagina:
        print("Não encontrei o script da página no index.html")
        return 1
    corpo = script_pagina.group(1)

    # Sem imports (já estão embutidos) e lendo a base de dentro do arquivo.
    corpo = re.sub(r'^\s*import\s+.*?;\s*$', "", corpo, flags=re.MULTILINE | re.DOTALL)
    corpo = corpo.replace(
        'const base = await (await fetch("./base.json", { cache: "force-cache" })).json();',
        "const base = BASE_EMBUTIDA;",
    )
    # Service worker e manifest não existem num arquivo solto.
    corpo = re.sub(
        r'if \("serviceWorker" in navigator.*?\n}\n', "", corpo, flags=re.DOTALL
    )

    novo_script = (
        "<script>\n"
        + modelo + "\n"
        + tsejs + "\n"
        + ponte.replace("__BASE__", json.dumps(base, ensure_ascii=False,
                                               separators=(",", ":")))
        + "\n" + corpo + "\n</script>"
    )
    html = html[:script_pagina.start()] + novo_script + html[script_pagina.end():]

    # Referências a arquivos que não acompanham o HTML solto.
    html = re.sub(r'<link rel="manifest"[^>]*>\n?', "", html)
    html = re.sub(r'<link rel="icon"[^>]*>\n?', "", html)
    html = re.sub(r'<link rel="apple-touch-icon"[^>]*>\n?', "", html)

    # Os cartões de instalação só fazem sentido no site.
    html = html.replace('<div class="cartao instalar" id="cartaoInstalar">',
                        '<div class="cartao instalar" id="cartaoInstalar" hidden>')
    html = html.replace('<div class="cartao instalar" id="cartaoIOS">',
                        '<div class="cartao instalar" id="cartaoIOS" hidden>')

    with open(SAIDA, "w", encoding="utf-8") as fh:
        fh.write(html)

    tam = os.path.getsize(SAIDA)
    print("Arquivo único gerado: %s" % SAIDA)
    print("  tamanho: %.0f KB" % (tam / 1024))
    print("  %d municípios embutidos" % len(base["ufs"]))
    print("\n  Pode ser aberto direto do celular, mandado por WhatsApp ou")
    print("  guardado num pendrive. Não precisa de servidor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
