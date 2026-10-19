"""
Gera os dois slides de divulgação para os stories do Instagram (1080 × 1920).

IDENTIDADE VISUAL — tirada do próprio perfil @oxe_eraassim
A marca é papel velho: fundo creme, serifa escura e pesada, vermelho de
tinta e o sol dourado do logo. Todas as capas dos reels são assim.

POR QUE DOIS SLIDES
Num story a pessoa decide em uns cinco segundos se fica ou passa. Tudo numa
tela só vira parede de texto e ninguém lê a parte que mais importa, que é a
do erro. Então o primeiro slide diz o que é e avisa que não é oficial; o
segundo mostra o tamanho do erro e o que a página tem.

HONESTIDADE DA PEÇA
Divulgar "dá para saber quem ganhou com 5% apurado" venderia uma certeza que
o modelo não tem: com 5% apurado o erro médio nos backtests foi de 0,96
ponto percentual e chegou a 1,83 em 2014. Numa disputa decidida por menos
que isso, a projeção pode apontar o candidato errado. Quem vê o story
precisa saber disso antes de abrir a página, não depois.

Os números saem de programa/backtest.py --ano 2006 2010 2014 2018 2022 e
devem ser recalculados se o modelo mudar.

Uso:  python3 gerar_stories.py
"""

from __future__ import annotations

import json
import os

import cairosvg

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

L, A = 1080, 1920

PAPEL = "#f0e8d8"
PAPEL_2 = "#e4dac4"
TINTA = "#1c1b19"
TINTA_FRACA = "#6b6456"
VERMELHO = "#c8433a"
DOURADO = "#e09a62"
VERDE = "#3d7a4f"
VERDE_CLARO = "#7cc492"

SERIF = "Lora, Georgia, serif"

ENDERECO = "oxeeraassim.github.io/apuracao"
PERFIL = "@oxe_eraassim"

NIVEL = 0.58

ERROS = [("5%", "0,96", "1,83"),
         ("20%", "0,73", "1,57"),
         ("50%", "0,30", "0,79"),
         ("75%", "0,14", "0,43")]


def txt(x, y, t, tam, peso="400", cor=TINTA, anc="middle", esp="0", op="1"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anc}" fill="{cor}" '
            f'font-family="{SERIF}" font-size="{tam}" font-weight="{peso}" '
            f'letter-spacing="{esp}" opacity="{op}">{t}</text>')


def sol(cx, cy, r):
    p = [f'<circle cx="{cx}" cy="{cy}" r="{r * 0.46:.1f}" fill="{DOURADO}"/>']
    for i, rr in enumerate([r * 0.66, r * 0.84, r]):
        p.append(f'<path d="M {cx - rr:.1f} {cy} A {rr:.1f} {rr:.1f} 0 0 1 '
                 f'{cx + rr:.1f} {cy}" fill="none" stroke="{DOURADO}" '
                 f'stroke-width="{7 - i}" opacity="{0.9 - i * 0.18:.2f}"/>')
    return "".join(p)


def cabecalho():
    return ("".join([
        txt(88, 122, "OXE,", 32, "700", TINTA, "start"),
        txt(172, 122, "era assim?", 26, "400", TINTA_FRACA, "start"),
        sol(L - 120, 112, 42),
        f'<rect x="88" y="152" width="{L - 176}" height="3" fill="{TINTA}" '
        f'opacity="0.18"/>']))


def rodape(escuro=True):
    cor = TINTA if escuro else VERMELHO
    return "".join([
        f'<rect x="0" y="1786" width="{L}" height="134" fill="{cor}"/>',
        txt(L / 2, 1843, ENDERECO, 35, "700", PAPEL),
        txt(L / 2, 1890, PERFIL, 25, "400", PAPEL, esp="2", op="0.8")])


def mapa_svg(dy, alvo):
    with open(os.path.join(RAIZ, "mapa.json"), encoding="utf-8") as fh:
        mapa = json.load(fh)
    _, _, lm, am = (float(v) for v in mapa["viewBox"].split())
    esc = alvo / max(lm, am)
    dx = (L - lm * esc) / 2
    formas = "".join(f'<path d="{d}"/>' for d in mapa["ufs"].values())
    corte = dy + am * esc * (1 - NIVEL)
    return ("".join([
        '<defs>',
        f'<linearGradient id="nivel" x1="0" y1="{dy}" x2="0" y2="{dy + am * esc}"'
        f' gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{PAPEL_2}"/>'
        f'<stop offset="{1 - NIVEL}" stop-color="{PAPEL_2}"/>'
        f'<stop offset="{1 - NIVEL}" stop-color="{VERDE_CLARO}"/>'
        f'<stop offset="1" stop-color="{VERDE}"/></linearGradient>',
        '<clipPath id="br" clipPathUnits="userSpaceOnUse">'
        f'<g transform="translate({dx:.1f},{dy:.1f}) scale({esc:.5f})">{formas}</g>'
        '</clipPath></defs>',
        '<g clip-path="url(#br)">',
        f'<rect x="0" y="{dy}" width="{L}" height="{am * esc}" fill="url(#nivel)"/>',
        f'<rect x="0" y="{corte - 3}" width="{L}" height="6" fill="{PAPEL}" '
        f'opacity="0.85"/>',
        f'<rect x="0" y="{dy}" width="{L}" height="{am * esc}" fill="none" '
        f'stroke="{TINTA}" stroke-width="6" opacity="0.25"/>',
        '</g>']))


def slide_1() -> str:
    """O problema que a página resolve. Este é o slide que para o dedo."""
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         f'<rect width="{L}" height="{A}" fill="{PAPEL}"/>',
         cabecalho()]

    # O gancho é o problema, não a promessa. "Vamos antecipar o resultado"
    # soa como quem vai dar o vencedor antes da hora — e é assim que um
    # print da tela vira munição de campanha. "O número engana" desperta a
    # mesma curiosidade e descreve o que a página realmente faz.
    p.append(txt(L / 2, 290, "No começo da apuração,", 62, "700"))
    p.append(txt(L / 2, 364, "o número engana", 62, "700"))
    p.append(f'<rect x="{L / 2 - 80}" y="406" width="160" height="4" '
             f'fill="{VERMELHO}"/>')

    p.append(txt(L / 2, 474, "As urnas não terminam de contar todas na mesma", 29,
                 "400", TINTA))
    p.append(txt(L / 2, 514, "hora. Nos primeiros minutos, o percentual oficial", 29,
                 "400", TINTA))
    p.append(txt(L / 2, 554, "mostra só os lugares que já fecharam a contagem", 29,
                 "400", TINTA))
    p.append(txt(L / 2, 594, "— e não o país inteiro.", 29, "700", TINTA))

    p.append(mapa_svg(656, 430))

    p.append(txt(L / 2, 1212, "Um algoritmo preditivo calcula o que ainda falta", 29,
                 "400", TINTA_FRACA))
    p.append(txt(L / 2, 1252, "de cada lugar e estima onde a apuração vai", 29,
                 "400", TINTA_FRACA))
    p.append(txt(L / 2, 1292, "terminar, se ajustando a cada urna contada.", 29,
                 "400", TINTA_FRACA))

    y = 1360
    p.append(f'<rect x="88" y="{y}" width="4" height="118" fill="{VERDE}"/>')
    p.append(txt(126, y + 34, "A APURAÇÃO", 25, "700", VERDE, "start", esp="3"))
    p.append(txt(126, y + 76, "Dados oficiais do TSE, lidos ao vivo,", 28, "400",
                 TINTA, "start"))
    p.append(txt(126, y + 112, "com a margem sempre ao lado do número.", 28, "400",
                 TINTA, "start"))

    y = 1520
    p.append(f'<rect x="88" y="{y}" width="4" height="158" fill="{VERMELHO}"/>')
    p.append(txt(126, y + 34, "AS PESQUISAS", 25, "700", VERMELHO, "start", esp="3"))
    p.append(txt(126, y + 76, "Sempre as mais recentes, com a porcentagem", 28,
                 "400", TINTA, "start"))
    p.append(txt(126, y + 112, "ponderada por pesquisa — atualizada assim", 28,
                 "400", TINTA, "start"))
    p.append(txt(126, y + 148, "que uma nova é divulgada.", 28, "400", TINTA,
                 "start"))

    p.append(rodape())
    p.append("</svg>")
    return "".join(p)


def slide_2() -> str:
    """O tamanho do erro e a postura da página."""
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         f'<rect width="{L}" height="{A}" fill="{PAPEL}"/>',
         cabecalho()]

    p.append(txt(L / 2, 272, "E pode errar.", 58, "700"))
    p.append(txt(L / 2, 342, "Veja o quanto.", 58, "700"))
    p.append(txt(L / 2, 396, "Erro nas últimas 5 eleições, em pontos percentuais",
                 26, "400", TINTA_FRACA))

    topo = 440
    alt = 88
    p.append(f'<rect x="72" y="{topo}" width="{L - 144}" height="{alt * 5 + 16}" '
             f'rx="14" fill="{PAPEL_2}"/>')
    p.append(txt(195, topo + 56, "APURADO", 25, "700", TINTA_FRACA, esp="2"))
    p.append(txt(610, topo + 56, "EM MÉDIA", 25, "700", TINTA_FRACA, esp="2"))
    p.append(txt(890, topo + 56, "PIOR CASO", 25, "700", TINTA_FRACA, esp="2"))
    for i, (marco, medio, pior) in enumerate(ERROS):
        y = topo + alt * (i + 1) + 58
        p.append(f'<rect x="100" y="{y - 60}" width="{L - 200}" height="2" '
                 f'fill="{TINTA}" opacity="0.12"/>')
        p.append(txt(195, y, marco, 42, "700", TINTA))
        p.append(txt(610, y, "± " + medio, 42, "700", VERDE))
        p.append(txt(890, y, "± " + pior, 42, "400", TINTA_FRACA))

    y = topo + alt * 5 + 86
    p.append(txt(L / 2, y, "Numa disputa decidida por menos que isso, a", 29,
                 "400", TINTA))
    p.append(txt(L / 2, y + 40, "projeção pode apontar o candidato errado", 29,
                 "700", TINTA))
    p.append(txt(L / 2, y + 80, "no começo da noite.", 29, "700", TINTA))

    # ---- a postura, que é o que protege a página ----
    y = 1130
    p.append(f'<rect x="60" y="{y}" width="{L - 120}" height="268" rx="12" '
             f'fill="none" stroke="{TINTA}" stroke-width="3" opacity="0.35"/>')
    p.append(txt(L / 2, y + 62, "SEM LADO", 30, "700", TINTA, esp="5"))
    p.append(txt(L / 2, y + 118, "A página não torce por ninguém e não", 29, "400",
                 TINTA))
    p.append(txt(L / 2, y + 158, "declara vencedor. Mostra sempre a margem", 29,
                 "400", TINTA))
    p.append(txt(L / 2, y + 198, "junto do número — e, enquanto a diferença", 29,
                 "400", TINTA))
    p.append(txt(L / 2, y + 238, "couber nela, diz que ainda não dá para saber.",
                 29, "700", TINTA))

    p.append(f'<rect x="60" y="1456" width="{L - 120}" height="230" rx="12" '
             f'fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 1544, "ISTO NÃO É", 58, "700", PAPEL, esp="2"))
    p.append(txt(L / 2, 1612, "RESULTADO OFICIAL", 58, "700", PAPEL, esp="2"))
    p.append(txt(L / 2, 1656, "O resultado que vale é sempre o do TSE.", 27, "400",
                 PAPEL, op="0.92"))

    p.append(rodape(escuro=False))
    p.append("</svg>")
    return "".join(p)


def main() -> None:
    saida = os.path.join(RAIZ, "divulgacao")
    os.makedirs(saida, exist_ok=True)
    for nome, svg in [("stories-1-o-que-e", slide_1()),
                      ("stories-2-margem-de-erro", slide_2())]:
        png = os.path.join(saida, nome + ".png")
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=png,
                         output_width=L, output_height=A)
        with open(os.path.join(saida, nome + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("  " + png)


if __name__ == "__main__":
    main()
