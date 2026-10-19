"""
Gera o slide de divulgação para os stories do Instagram (1080 × 1920).

IDENTIDADE VISUAL — tirada do próprio perfil @oxe_eraassim
Papel velho: fundo creme, serifa escura e pesada, vermelho de tinta e o sol
dourado do logo. Todas as capas dos reels são assim.

POR QUE UM SLIDE SÓ
A versão anterior tinha dois, e o segundo trazia uma tabela com erro médio e
pior caso em quatro marcos de apuração. Informação correta, mas no lugar
errado: num story a pessoa decide em segundos, e uma tabela de números faz
ela passar. Quem passa não lê nem a parte técnica nem a ressalva.

A precisão continua aqui, só que dita como se diz para alguém na rua — "96
em cada 100" — e com o limite colado nela, na mesma frase. Quem quiser o
detalhe encontra a margem na própria página, ao lado de cada número.

ORDEM DA LEITURA
1. o problema      por que o número do começo engana
2. a solução       o que o modelo faz, em três linhas
3. a precisão      quanto acerta, e quando erra
4. o aviso         não é resultado oficial
Essa ordem importa: a precisão só aparece depois de a pessoa entender o que
está sendo medido, e nunca sem o limite ao lado.

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


def mapa_svg(dy, alvo):
    with open(os.path.join(RAIZ, "mapa.json"), encoding="utf-8") as fh:
        mapa = json.load(fh)
    _, _, lm, am = (float(v) for v in mapa["viewBox"].split())
    esc = alvo / max(lm, am)
    dx = (L - lm * esc) / 2
    formas = "".join(f'<path d="{d}"/>' for d in mapa["ufs"].values())
    corte = dy + am * esc * (1 - NIVEL)
    return "".join([
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
        '</g>'])


def montar() -> str:
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         f'<rect width="{L}" height="{A}" fill="{PAPEL}"/>']

    # ---- assinatura da página ----
    p.append(txt(84, 118, "OXE,", 32, "700", TINTA, "start"))
    p.append(txt(168, 118, "era assim?", 26, "400", TINTA_FRACA, "start"))
    p.append(sol(L - 116, 108, 42))
    p.append(f'<rect x="84" y="148" width="{L - 168}" height="3" fill="{TINTA}" '
             f'opacity="0.18"/>')

    # ---- 1. o problema ----
    p.append(txt(L / 2, 264, "No começo da apuração,", 58, "700"))
    p.append(txt(L / 2, 334, "o número engana", 58, "700"))
    p.append(f'<rect x="{L / 2 - 70}" y="372" width="140" height="4" '
             f'fill="{VERMELHO}"/>')

    # ---- 2. a explicação, em três frases curtas ----
    p.append(txt(L / 2, 440, "As urnas não terminam de contar", 31, "400", TINTA))
    p.append(txt(L / 2, 482, "todas na mesma hora. Nos primeiros", 31, "400", TINTA))
    p.append(txt(L / 2, 524, "minutos, o número oficial mostra só", 31, "400", TINTA))
    p.append(txt(L / 2, 566, "uma parte do país.", 31, "700", TINTA))

    p.append(mapa_svg(626, 410))

    p.append(txt(L / 2, 1130, "Esta página calcula o que ainda falta contar", 31,
                 "400", TINTA))
    p.append(txt(L / 2, 1172, "em cada lugar e completa o quadro, se", 31, "400",
                 TINTA))
    p.append(txt(L / 2, 1214, "ajustando a cada urna que entra.", 31, "400", TINTA))

    # ---- 3. a precisão, com o limite na mesma respiração ----
    p.append(f'<rect x="60" y="1274" width="{L - 120}" height="266" rx="14" '
             f'fill="{PAPEL_2}"/>')
    p.append(txt(L / 2, 1342, "Com 5% das urnas contadas,", 31, "400", TINTA))
    p.append(txt(L / 2, 1346 + 76, "acertou 96 em cada 100", 54, "700", VERDE))
    p.append(txt(L / 2, 1472, "em mil eleições de teste. Mas pode errar quando", 27,
                 "400", TINTA_FRACA))
    p.append(txt(L / 2, 1508, "a disputa é apertada — e aí a página avisa.", 27,
                 "400", TINTA_FRACA))

    # ---- 4. o aviso ----
    p.append(f'<rect x="60" y="1576" width="{L - 120}" height="180" rx="12" '
             f'fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 1648, "ISTO NÃO É RESULTADO OFICIAL", 42, "700", PAPEL,
                 esp="1"))
    p.append(txt(L / 2, 1706, "O resultado que vale é sempre o do TSE.", 28, "400",
                 PAPEL, op="0.92"))

    # ---- link ----
    p.append(f'<rect x="0" y="1786" width="{L}" height="134" fill="{TINTA}"/>')
    p.append(txt(L / 2, 1843, ENDERECO, 35, "700", PAPEL))
    p.append(txt(L / 2, 1890, PERFIL, 25, "400", PAPEL, esp="2", op="0.8"))

    p.append("</svg>")
    return "".join(p)


def main() -> None:
    saida = os.path.join(RAIZ, "divulgacao")
    os.makedirs(saida, exist_ok=True)
    svg = montar()
    png = os.path.join(saida, "stories-apuracao.png")
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=png,
                     output_width=L, output_height=A)
    with open(os.path.join(saida, "stories-apuracao.svg"), "w",
              encoding="utf-8") as fh:
        fh.write(svg)
    print("  " + png)


if __name__ == "__main__":
    main()
