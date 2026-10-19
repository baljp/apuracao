"""
Gera a imagem de divulgação para os stories do Instagram (1080 × 1920).

A peça é escura e usa o mesmo mapa enchendo de baixo para cima que está no
ícone do aplicativo: quem vir o story e depois instalar reconhece a mesma
coisa. Verde continua significando andamento da apuração, nunca candidato —
um story eleitoral em azul ou vermelho vira propaganda, e a página não é.

O texto promete o que a página entrega e nada além: projeção é estimativa,
não resultado. Exagerar aqui é o jeito mais rápido de queimar a credibilidade
da página justamente na noite em que ela precisa ter alguma.

Uso:  python3 gerar_stories.py
"""

from __future__ import annotations

import json
import os

import cairosvg

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

L, A = 1080, 1920

FUNDO_1 = "#16203A"
FUNDO_2 = "#070A12"
VERDE = "#34D399"
VERDE_2 = "#10B981"
CINZA_MAPA = "#2E3A52"
BRANCO = "#FFFFFF"
SUAVE = "#9FB0CC"
LINHA_AGUA = "#A7F3D0"

ENDERECO = "baljp.github.io/apuracao"
PERFIL = "@oxe_eraassim"

NIVEL = 0.58   # quanto do mapa aparece "apurado"


def texto(x, y, t, tam, peso="600", cor=BRANCO, anc="middle", esp="0", op="1"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anc}" fill="{cor}" '
            f'font-family="Helvetica Neue,Helvetica,Arial" font-size="{tam}" '
            f'font-weight="{peso}" letter-spacing="{esp}" opacity="{op}">{t}</text>')


def montar() -> str:
    with open(os.path.join(RAIZ, "mapa.json"), encoding="utf-8") as fh:
        mapa = json.load(fh)
    _, _, lm, am = (float(v) for v in mapa["viewBox"].split())

    # O mapa ocupa a faixa central da peça.
    alvo = 560.0
    esc = alvo / max(lm, am)
    dx = (L - lm * esc) / 2
    dy = 560
    formas = "".join(f'<path d="{d}"/>' for d in mapa["ufs"].values())
    corte = dy + am * esc * (1 - NIVEL)

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         '<defs>',
         f'<linearGradient id="ceu" x1="0" y1="0" x2="0.4" y2="1">'
         f'<stop offset="0" stop-color="{FUNDO_1}"/>'
         f'<stop offset="1" stop-color="{FUNDO_2}"/></linearGradient>',
         f'<linearGradient id="nivel" x1="0" y1="{dy}" x2="0" y2="{dy + am * esc}"'
         f' gradientUnits="userSpaceOnUse">'
         f'<stop offset="0" stop-color="{CINZA_MAPA}"/>'
         f'<stop offset="{1 - NIVEL}" stop-color="{CINZA_MAPA}"/>'
         f'<stop offset="{1 - NIVEL}" stop-color="{VERDE}"/>'
         f'<stop offset="1" stop-color="{VERDE_2}"/></linearGradient>',
         '<clipPath id="br" clipPathUnits="userSpaceOnUse">'
         f'<g transform="translate({dx:.1f},{dy:.1f}) scale({esc:.5f})">{formas}</g>'
         '</clipPath>',
         '</defs>',
         f'<rect width="{L}" height="{A}" fill="url(#ceu)"/>']

    # ---- topo ----
    p.append(texto(L / 2, 180, "DOMINGO, 25 DE OUTUBRO", 34, "700", VERDE, esp="4"))
    p.append(texto(L / 2, 290, "O resultado", 88, "700"))
    p.append(texto(L / 2, 390, "antes do fim", 88, "700"))
    p.append(texto(L / 2, 490, "da apuração", 88, "700"))

    # ---- mapa ----
    p.append('<g clip-path="url(#br)">')
    p.append(f'<rect x="0" y="{dy}" width="{L}" height="{am * esc}" fill="url(#nivel)"/>')
    p.append(f'<rect x="0" y="{corte - 4}" width="{L}" height="8" '
             f'fill="{LINHA_AGUA}" opacity="0.9"/>')
    p.append('</g>')

    # ---- as duas coisas que a página faz ----
    y = 1240
    p.append(f'<rect x="90" y="{y}" width="4" height="150" fill="{VERDE}" rx="2"/>')
    p.append(texto(130, y + 36, "PROJEÇÃO AO VIVO", 30, "700", VERDE, "start", esp="2"))
    p.append(texto(130, y + 86, "O Sul conta rápido, o Nordeste demora.", 33, "500",
                   BRANCO, "start"))
    p.append(texto(130, y + 130, "O modelo corrige isso e mostra onde vai dar.", 33,
                   "500", BRANCO, "start"))

    y = 1430
    p.append(f'<rect x="90" y="{y}" width="4" height="150" fill="{SUAVE}" rx="2"/>')
    p.append(texto(130, y + 36, "PESQUISAS", 30, "700", SUAVE, "start", esp="2"))
    p.append(texto(130, y + 86, "Vários institutos num lugar só, com média", 33, "500",
                   BRANCO, "start"))
    p.append(texto(130, y + 130, "que pesa mais as recentes e as maiores.", 33, "500",
                   BRANCO, "start"))

    # ---- rodapé ----
    p.append(texto(L / 2, 1690, "É uma estimativa estatística, não o resultado oficial.",
                   27, "500", SUAVE, op="0.8"))
    p.append(f'<rect x="{L / 2 - 310}" y="1730" width="620" height="92" rx="46" '
             f'fill="{VERDE}"/>')
    p.append(texto(L / 2, 1790, ENDERECO, 40, "700", "#06281D"))
    p.append(texto(L / 2, 1878, PERFIL, 30, "600", SUAVE, esp="1"))

    p.append("</svg>")
    return "".join(p)


def main() -> None:
    svg = montar()
    png = os.path.join(RAIZ, "divulgacao", "stories-apuracao.png")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=png,
                     output_width=L, output_height=A)
    with open(png.replace(".png", ".svg"), "w", encoding="utf-8") as fh:
        fh.write(svg)
    print("  " + png)


if __name__ == "__main__":
    main()
