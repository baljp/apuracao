"""
Gera a imagem de divulgação para os stories do Instagram (1080 × 1920).

IDENTIDADE VISUAL
Tirada da Biblioteca do Oxe (oxeeraassim.github.io), que é a mesma marca:
fundo quase preto #191a1f, creme de papel velho #e8e2d3, verde #7cc492 e
terracota #e06a5f. A tipografia de lá é Zilla Slab com Literata; aqui a
substituta é a Lora, da mesma família editorial com serifa — quem vê o story
e depois abre a Biblioteca reconhece a mesma mão.

Verde continua significando andamento da apuração e nunca candidato. Um story
eleitoral em azul ou vermelho vira propaganda, e a página não é.

SOBRE O TEXTO
A primeira versão dizia "o Sul conta rápido, o Nordeste demora". Soa como
julgamento de região, e nem é a explicação certa. O que acontece é mais
simples e vale para o país inteiro: as urnas não terminam todas na mesma
hora, então o número do começo mostra só os lugares que já fecharam a
contagem. O modelo calcula o que falta e vai montando o cenário completo.

O texto promete o que a página entrega e nada além, inclusive a linha de que
projeção é estimativa. Exagerar na divulgação é o jeito mais rápido de
queimar a credibilidade da página na noite em que ela precisa ter alguma.

Uso:  python3 gerar_stories.py
"""

from __future__ import annotations

import json
import os

import cairosvg

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

L, A = 1080, 1920

# Paleta da Biblioteca do Oxe.
TINTA = "#191a1f"
TINTA_2 = "#24252c"
CREME = "#e8e2d3"
CREME_FORTE = "#fbf8f1"
VERDE = "#7cc492"
VERDE_FUNDO = "#3d7a4f"
TERRACOTA = "#e06a5f"
CINZA = "#a3a6b2"
MAPA_FALTA = "#3a3b44"

SERIF = "Lora, Georgia, serif"

ENDERECO = "oxeeraassim.github.io/apuracao"
PERFIL = "@oxe_eraassim"

NIVEL = 0.58


def txt(x, y, t, tam, peso="400", cor=CREME, anc="middle", esp="0", op="1",
        fonte=SERIF):
    return (f'<text x="{x}" y="{y}" text-anchor="{anc}" fill="{cor}" '
            f'font-family="{fonte}" font-size="{tam}" font-weight="{peso}" '
            f'letter-spacing="{esp}" opacity="{op}">{t}</text>')


def montar() -> str:
    with open(os.path.join(RAIZ, "mapa.json"), encoding="utf-8") as fh:
        mapa = json.load(fh)
    _, _, lm, am = (float(v) for v in mapa["viewBox"].split())

    alvo = 520.0
    esc = alvo / max(lm, am)
    dx = (L - lm * esc) / 2
    dy = 600
    formas = "".join(f'<path d="{d}"/>' for d in mapa["ufs"].values())
    corte = dy + am * esc * (1 - NIVEL)

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         '<defs>',
         f'<linearGradient id="fundo" x1="0" y1="0" x2="0.3" y2="1">'
         f'<stop offset="0" stop-color="{TINTA_2}"/>'
         f'<stop offset="1" stop-color="{TINTA}"/></linearGradient>',
         f'<linearGradient id="nivel" x1="0" y1="{dy}" x2="0" y2="{dy + am * esc}"'
         f' gradientUnits="userSpaceOnUse">'
         f'<stop offset="0" stop-color="{MAPA_FALTA}"/>'
         f'<stop offset="{1 - NIVEL}" stop-color="{MAPA_FALTA}"/>'
         f'<stop offset="{1 - NIVEL}" stop-color="{VERDE}"/>'
         f'<stop offset="1" stop-color="{VERDE_FUNDO}"/></linearGradient>',
         '<clipPath id="br" clipPathUnits="userSpaceOnUse">'
         f'<g transform="translate({dx:.1f},{dy:.1f}) scale({esc:.5f})">{formas}</g>'
         '</clipPath>',
         '</defs>',
         f'<rect width="{L}" height="{A}" fill="url(#fundo)"/>']

    # ---- topo ----
    p.append(f'<rect x="{L / 2 - 180}" y="150" width="360" height="52" rx="26" '
             f'fill="none" stroke="{TERRACOTA}" stroke-width="2"/>')
    p.append(txt(L / 2, 186, "25 DE OUTUBRO", 28, "700", TERRACOTA, esp="5"))

    p.append(txt(L / 2, 320, "O resultado antes", 76, "700", CREME_FORTE))
    p.append(txt(L / 2, 410, "do fim da apuração", 76, "700", CREME_FORTE))
    p.append(txt(L / 2, 490, "Uma projeção que se ajusta a cada urna contada.",
                 31, "400", CINZA))

    # ---- mapa ----
    p.append('<g clip-path="url(#br)">')
    p.append(f'<rect x="0" y="{dy}" width="{L}" height="{am * esc}" fill="url(#nivel)"/>')
    p.append(f'<rect x="0" y="{corte - 3}" width="{L}" height="6" '
             f'fill="{CREME}" opacity="0.75"/>')
    p.append('</g>')

    # ---- o que a página faz ----
    y = 1225
    p.append(f'<rect x="88" y="{y}" width="3" height="166" fill="{VERDE}"/>')
    p.append(txt(128, y + 34, "A APURAÇÃO", 27, "700", VERDE, "start", esp="3"))
    p.append(txt(128, y + 88, "As urnas não terminam todas na mesma hora.",
                 31, "400", CREME, "start"))
    p.append(txt(128, y + 130, "Um modelo preditivo calcula o que ainda falta",
                 31, "400", CREME, "start"))
    p.append(txt(128, y + 172, "e vai montando o cenário completo do país.",
                 31, "400", CREME, "start"))

    y = 1455
    p.append(f'<rect x="88" y="{y}" width="3" height="124" fill="{TERRACOTA}"/>')
    p.append(txt(128, y + 34, "AS PESQUISAS", 27, "700", TERRACOTA, "start", esp="3"))
    p.append(txt(128, y + 88, "Vários institutos num lugar só, com média",
                 31, "400", CREME, "start"))
    p.append(txt(128, y + 130, "que pesa mais as recentes e as maiores.",
                 31, "400", CREME, "start"))

    # ---- rodapé ----
    # O aviso não é letra miúda de rodapé: é o que separa a página de um
    # perfil que chuta resultado. Fica em caixa própria, com o mesmo peso de
    # leitura do resto, e diz as duas coisas que importam — que o modelo
    # pode errar, e quem dá a palavra final.
    y = 1640
    p.append(f'<rect x="88" y="{y}" width="{L - 176}" height="118" rx="14" '
             f'fill="none" stroke="{MAPA_FALTA}" stroke-width="2"/>')
    p.append(txt(L / 2, y + 48, "Modelo preditivo: é uma estimativa e pode errar.",
                 27, "700", CREME, op="0.95"))
    p.append(txt(L / 2, y + 88, "O resultado que vale é sempre o do TSE.",
                 27, "400", CINZA))

    p.append(f'<rect x="{L / 2 - 340}" y="1790" width="680" height="84" rx="42" '
             f'fill="{CREME}"/>')
    p.append(txt(L / 2, 1843, ENDERECO, 33, "700", TINTA))
    p.append(txt(L / 2, 1902, PERFIL, 26, "400", CINZA, esp="2"))

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
