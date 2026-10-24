"""
Carimba a versão dos arquivos do site a partir do conteúdo deles.

O problema que isto resolve: o GitHub Pages serve tudo com 10 minutos de
cache. Sem um carimbo na URL, uma correção publicada só chegaria ao visitante
até 10 minutos depois — inaceitável numa noite de apuração, em que um erro
precisa ser consertado na hora.

A versão é o hash do conteúdo, não um número que alguém lembra de aumentar.
Se o arquivo mudou, a URL muda e o navegador busca de novo; se não mudou, a
URL continua igual e o cache é aproveitado. Nada para lembrar, nada para
esquecer.

Roda sozinho antes de cada publicação (veja .github/workflows/versionar.yml),
e pode ser rodado à mão:

    python3 programa/versionar.py
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

# Arquivos cujo endereço leva carimbo de versão dentro do index.html.
MODULOS = ["modelo.js", "tse.js", "pesquisas.js"]
# O que entra no cálculo da versão do service worker: se qualquer um mudar,
# o cache inteiro do aparelho é trocado.
DO_CASCO = MODULOS + ["index.html", "base.json", "mapa.json", "mapa-mun.json",
                      "fonte.css", "sw.js"]


def hash_de(nome: str) -> str:
    """
    Hash do conteúdo, ignorando os próprios carimbos de versão.

    Sem essa limpeza o cálculo seria circular: carimbar o index.html mudaria
    o seu hash, que mudaria o carimbo, que mudaria o hash de novo — e cada
    publicação geraria um commit novo sem que nada de verdade tivesse
    mudado.
    """
    caminho = os.path.join(RAIZ, nome)
    if not os.path.exists(caminho):
        return "0"
    with open(caminho, "rb") as fh:
        dados = fh.read()
    if nome.endswith((".html", ".js")):
        texto = dados.decode("utf-8", "replace")
        texto = re.sub(r'\?v=[0-9a-f]{4,}', "", texto)
        texto = re.sub(r'const VERSAO = "[^"]*";', 'const VERSAO = "";', texto)
        dados = texto.encode("utf-8")
    return hashlib.sha256(dados).hexdigest()[:10]


def main() -> int:
    index = os.path.join(RAIZ, "index.html")
    if not os.path.exists(index):
        print("index.html não encontrado")
        return 1

    with open(index, encoding="utf-8") as fh:
        html = fh.read()
    original = html

    # Cada módulo recebe o hash do seu próprio conteúdo.
    for modulo in MODULOS:
        h = hash_de(modulo)
        html = re.sub(
            r'(["\'])\./%s(?:\?v=[^"\']*)?\1' % re.escape(modulo),
            lambda m, h=h, mod=modulo: '%s./%s?v=%s%s' % (m.group(1), mod, h, m.group(1)),
            html,
        )

    # O service worker recebe o hash de tudo somado.
    juntos = hashlib.sha256(
        "".join(hash_de(n) for n in sorted(DO_CASCO)).encode()
    ).hexdigest()[:10]
    html = re.sub(r'(["\'])\./sw\.js(?:\?v=[^"\']*)?\1',
                  r'\1./sw.js?v=%s\1' % juntos, html)

    with open(index, "w", encoding="utf-8") as fh:
        fh.write(html)

    # O nome do cache também vira o hash: ao ativar, o service worker apaga
    # todos os caches antigos, porque nenhum deles bate com o nome novo.
    sw = os.path.join(RAIZ, "sw.js")
    if os.path.exists(sw):
        with open(sw, encoding="utf-8") as fh:
            codigo = fh.read()
        novo = re.sub(r'const VERSAO = "[^"]*";',
                      'const VERSAO = "apuracao-%s";' % juntos, codigo)
        if novo != codigo:
            with open(sw, "w", encoding="utf-8") as fh:
                fh.write(novo)

    print("Versões carimbadas:")
    for modulo in MODULOS:
        print("  %-16s %s" % (modulo, hash_de(modulo)))
    print("  %-16s %s" % ("(casco/sw)", juntos))
    print("mudou o index.html: %s" % ("sim" if html != original else "não"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
