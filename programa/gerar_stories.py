"""
Gera o slide de divulgação para os stories do Instagram (1080 × 1920).

IDENTIDADE VISUAL — tirada do próprio perfil @oxe_eraassim
Papel velho: fundo creme, serifa escura e pesada, vermelho de tinta e o sol
dourado do logo. Todas as capas dos reels são assim.

POR QUE SEM NÚMEROS
Versões anteriores traziam a tabela de erro e depois o "acertou 96 em cada
100". Informação correta, mas num story ela trabalha contra: número pede
leitura atenta, e quem está passando o dedo não dá essa atenção — então
some tanto o número quanto a ressalva que vinha com ele.

A peça agora explica o problema e diz que existe um modelo tentando
corrigi-lo. Nada de desempenho, nada de promessa: só o convite para ver. A
precisão, a margem e o aviso de quando não dá para saber estão na página, ao
lado de cada número, que é onde eles têm como ser lidos com calma.

O que não sai em nenhuma versão: que isto não é resultado oficial.

SOBRE A EXPLICAÇÃO REGIONAL
"Cada lugar termina de contar no seu tempo" é o jeito honesto de dizer. A
versão que citava quais regiões contam antes soava como julgamento, e nem
era a explicação certa — o que importa é que os lugares terminam em tempos
diferentes, não quais terminam primeiro.

SOBRE O TAMANHO DO TEXTO
Story é leitura de passagem: ninguém para o dedo para ler um parágrafo. A
versão anterior tinha cinco linhas de explicação e quatro no cartão do
meio, e a chance de a pessoa ler até o fim caía a cada linha. Cortado para
três e três, com o mapa maior ocupando o espaço que sobrou — a imagem
segura o olho melhor do que a frase a mais.

O endereço aparece escrito no rodapé, mas texto em imagem não é clicável:
na hora de postar, vai também o adesivo de link do Instagram apontando para
a página. Sem ele, quem se interessa precisa digitar o endereço na mão, e
não digita.

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

    # ---- 2. a explicação ----
    p.append(txt(L / 2, 452, "Cada lugar termina de contar no seu", 34, "400", TINTA))
    p.append(txt(L / 2, 498, "tempo. Nos primeiros minutos, o número", 34, "400", TINTA))
    p.append(txt(L / 2, 544, "oficial mostra só uma parte do país.", 34, "700", TINTA))

    p.append(mapa_svg(610, 470))

    # ---- 3. o que fizemos, sem prometer desempenho ----
    p.append(f'<rect x="60" y="1150" width="{L - 120}" height="200" rx="14" '
             f'fill="{PAPEL_2}"/>')
    p.append(txt(L / 2, 1212, "Fizemos um modelo que tenta", 34, "400", TINTA))
    p.append(txt(L / 2, 1258, "corrigir essa distorção", 34, "700", TINTA))
    p.append(txt(L / 2, 1318, "Ele refaz a conta a cada urna que entra.", 28,
                 "400", TINTA_FRACA))

    p.append(txt(L / 2, 1432, "Acompanhe no domingo, a partir das 17h.", 31, "700",
                 VERDE))

    # ---- 4. o aviso ----
    # O aviso explica, em vez de só alertar. "Não é resultado oficial" avisa
    # mas não ensina: quem nunca ouviu falar em projeção continua sem saber o
    # que está vendo. Dizendo o que É — uma projeção, feita por um modelo — a
    # pessoa entende a natureza do número antes de olhar para ele, e a frase
    # seguinte diz de quem é a palavra final.
    p.append(f'<rect x="60" y="1510" width="{L - 120}" height="188" rx="12" '
             f'fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 1572, "É uma projeção, não o resultado", 38, "700", PAPEL))
    p.append(txt(L / 2, 1626, "Os números saem de um modelo preditivo.", 27, "400",
                 PAPEL, op="0.95"))
    p.append(txt(L / 2, 1664, "O resultado oficial é o do TSE — e é ele que vale.",
                 27, "400", PAPEL, op="0.95"))

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
