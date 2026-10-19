"""
Gera a imagem de divulgação para os stories do Instagram (1080 × 1920).

IDENTIDADE VISUAL — tirada do próprio perfil @oxe_eraassim
A marca é papel velho: fundo creme, texto em serifa escura e pesada, com
vermelho de tinta e dourado de sol nordestino nos acentos. As capas dos
reels são todas assim — faixa de texto creme em cima, foto embaixo.

A primeira versão desta arte foi feita escura, e estava simplesmente
invertida em relação à marca. Num feed onde tudo é creme, um story preto não
parece da mesma casa.

TOM
As capas do perfil falam como quem conta um caso, não como quem dá aula:
"Dizem que debaixo desta igreja começa um túnel de quase 20 km. Ninguém
nunca achou a saída." Frase curta, fato espantoso, português simples. A
chamada aqui segue isso — mas sem prometer o que a página não entrega.

O aviso de que é modelo preditivo e pode errar tem peso de leitura próprio,
não é letra miúda. É o que separa a página de um perfil que chuta resultado.

Uso:  python3 gerar_stories.py
"""

from __future__ import annotations

import json
import os

import cairosvg

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

L, A = 1080, 1920

# Paleta do perfil.
PAPEL = "#f0e8d8"        # o creme do fundo das capas
PAPEL_2 = "#e4dac4"      # creme mais fechado, para separar blocos
TINTA = "#1c1b19"        # o preto quente do texto
TINTA_FRACA = "#6b6456"
VERMELHO = "#c8433a"     # o "DO OXE" da Biblioteca
DOURADO = "#e09a62"      # o sol listrado do logo
VERDE = "#3d7a4f"        # apuração andando — nunca candidato
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
    """O sol listrado do logo da página, em miniatura."""
    p = [f'<circle cx="{cx}" cy="{cy}" r="{r * 0.46:.1f}" fill="{DOURADO}"/>']
    for i, rr in enumerate([r * 0.66, r * 0.84, r]):
        p.append(f'<path d="M {cx - rr:.1f} {cy} A {rr:.1f} {rr:.1f} 0 0 1 '
                 f'{cx + rr:.1f} {cy}" fill="none" stroke="{DOURADO}" '
                 f'stroke-width="{7 - i}" opacity="{0.9 - i * 0.18:.2f}"/>')
    return "".join(p)


def montar() -> str:
    with open(os.path.join(RAIZ, "mapa.json"), encoding="utf-8") as fh:
        mapa = json.load(fh)
    _, _, lm, am = (float(v) for v in mapa["viewBox"].split())

    alvo = 470.0
    esc = alvo / max(lm, am)
    dx = (L - lm * esc) / 2
    dy = 660
    formas = "".join(f'<path d="{d}"/>' for d in mapa["ufs"].values())
    corte = dy + am * esc * (1 - NIVEL)

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         '<defs>',
         f'<linearGradient id="nivel" x1="0" y1="{dy}" x2="0" y2="{dy + am * esc}"'
         f' gradientUnits="userSpaceOnUse">'
         f'<stop offset="0" stop-color="{PAPEL_2}"/>'
         f'<stop offset="{1 - NIVEL}" stop-color="{PAPEL_2}"/>'
         f'<stop offset="{1 - NIVEL}" stop-color="{VERDE_CLARO}"/>'
         f'<stop offset="1" stop-color="{VERDE}"/></linearGradient>',
         '<clipPath id="br" clipPathUnits="userSpaceOnUse">'
         f'<g transform="translate({dx:.1f},{dy:.1f}) scale({esc:.5f})">{formas}</g>'
         '</clipPath>',
         '</defs>',
         f'<rect width="{L}" height="{A}" fill="{PAPEL}"/>']

    # ---- assinatura da página, como nas capas dos reels ----
    p.append(txt(88, 130, "OXE,", 34, "700", TINTA, "start"))
    p.append(txt(178, 130, "era assim?", 27, "400", TINTA_FRACA, "start"))
    p.append(sol(L - 120, 118, 44))
    p.append(f'<rect x="88" y="162" width="{L - 176}" height="3" fill="{TINTA}" '
             f'opacity="0.18"/>')

    # ---- chamada ----
    p.append(txt(L / 2, 300, "Dá para saber quem", 70, "700"))
    p.append(txt(L / 2, 382, "ganhou com 5% das", 70, "700"))
    p.append(txt(L / 2, 464, "urnas contadas.", 70, "700"))
    p.append(f'<rect x="{L / 2 - 90}" y="512" width="180" height="4" '
             f'fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 580, "A gente fez a conta — e conferiu nas", 32, "400",
                 TINTA_FRACA))
    p.append(txt(L / 2, 622, "cinco últimas eleições presidenciais.", 32, "400",
                 TINTA_FRACA))

    # ---- mapa ----
    p.append('<g clip-path="url(#br)">')
    p.append(f'<rect x="0" y="{dy}" width="{L}" height="{am * esc}" fill="url(#nivel)"/>')
    p.append(f'<rect x="0" y="{corte - 3}" width="{L}" height="6" fill="{PAPEL}" '
             f'opacity="0.85"/>')
    p.append('</g>')
    # Contorno do país, para o mapa não boiar no creme.
    p.append(f'<g clip-path="url(#br)"><rect x="0" y="{dy}" width="{L}" '
             f'height="{am * esc}" fill="none" stroke="{TINTA}" stroke-width="6" '
             f'opacity="0.25"/></g>')

    # ---- o que a página faz ----
    y = 1240
    p.append(f'<rect x="88" y="{y}" width="4" height="160" fill="{VERDE}"/>')
    p.append(txt(126, y + 34, "A APURAÇÃO", 26, "700", VERDE, "start", esp="3"))
    p.append(txt(126, y + 86, "As urnas não terminam todas na mesma", 30, "400",
                 TINTA, "start"))
    p.append(txt(126, y + 126, "hora. Um modelo preditivo calcula o que", 30, "400",
                 TINTA, "start"))
    p.append(txt(126, y + 166, "falta e monta o cenário do país inteiro.", 30, "400",
                 TINTA, "start"))

    y = 1455
    p.append(f'<rect x="88" y="{y}" width="4" height="120" fill="{VERMELHO}"/>')
    p.append(txt(126, y + 34, "AS PESQUISAS", 26, "700", VERMELHO, "start", esp="3"))
    p.append(txt(126, y + 86, "Vários institutos num lugar só, com média", 30, "400",
                 TINTA, "start"))
    p.append(txt(126, y + 126, "que pesa mais as recentes e as maiores.", 30, "400",
                 TINTA, "start"))

    # ---- o aviso, com peso de leitura próprio ----
    y = 1632
    p.append(f'<rect x="88" y="{y}" width="{L - 176}" height="112" rx="10" '
             f'fill="{PAPEL_2}"/>')
    p.append(txt(L / 2, y + 46, "Modelo preditivo: é estimativa e pode errar.",
                 27, "700", TINTA))
    p.append(txt(L / 2, y + 84, "O resultado que vale é sempre o do TSE.",
                 27, "400", TINTA_FRACA))

    # ---- faixa do link, como o rodapé da Biblioteca ----
    p.append(f'<rect x="0" y="1786" width="{L}" height="134" fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 1843, ENDERECO, 35, "700", PAPEL))
    p.append(txt(L / 2, 1890, PERFIL, 25, "400", PAPEL, esp="2", op="0.85"))

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
