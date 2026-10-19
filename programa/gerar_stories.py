"""
Gera a imagem de divulgação para os stories do Instagram (1080 × 1920).

IDENTIDADE VISUAL — tirada do próprio perfil @oxe_eraassim
A marca é papel velho: fundo creme, serifa escura e pesada, vermelho de
tinta e o sol dourado do logo. Todas as capas dos reels são assim.

HONESTIDADE DA PEÇA
Esta arte divulga uma previsão de eleição, e por isso a parte mais
importante dela não é a chamada: é o aviso e a tabela de erro.

Divulgar "dá para saber quem ganhou com 5% apurado" seria vender uma certeza
que o modelo não tem. Nos backtests, com 5% apurado o erro médio foi de 0,96
ponto percentual e chegou a 1,83 em 2014 — numa disputa decidida por menos
que isso, a projeção pode apontar o candidato errado. Quem lê o story
precisa saber disso ANTES de abrir a página, não depois.

Daí a tabela: ela mostra o erro encolhendo conforme a apuração avança, que é
a informação que permite à pessoa decidir quando confiar. Os números saem
dos backtests das cinco últimas eleições presidenciais (programa/backtest.py
--ano 2006 2010 2014 2018 2022) e devem ser recalculados se o modelo mudar.

Uso:  python3 gerar_stories.py
"""

from __future__ import annotations

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

SERIF = "Lora, Georgia, serif"

ENDERECO = "oxeeraassim.github.io/apuracao"
PERFIL = "@oxe_eraassim"

# Erro da projeção nos backtests de 2006, 2010, 2014, 2018 e 2022.
# (apurado, erro médio, pior caso)
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


def montar() -> str:
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
         f'viewBox="0 0 {L} {A}">',
         f'<rect width="{L}" height="{A}" fill="{PAPEL}"/>']

    # ---- assinatura da página ----
    p.append(txt(88, 122, "OXE,", 32, "700", TINTA, "start"))
    p.append(txt(172, 122, "era assim?", 26, "400", TINTA_FRACA, "start"))
    p.append(sol(L - 120, 112, 42))
    p.append(f'<rect x="88" y="152" width="{L - 176}" height="3" fill="{TINTA}" '
             f'opacity="0.18"/>')

    # ---- chamada ----
    p.append(txt(L / 2, 272, "Vamos tentar antecipar", 60, "700"))
    p.append(txt(L / 2, 344, "o resultado da eleição", 60, "700"))
    p.append(f'<rect x="{L / 2 - 80}" y="388" width="160" height="4" '
             f'fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 452, "Um algoritmo preditivo acompanha a apuração e", 30,
                 "400", TINTA_FRACA))
    p.append(txt(L / 2, 492, "estima onde ela vai terminar. É uma tentativa,", 30,
                 "400", TINTA_FRACA))
    p.append(txt(L / 2, 532, "baseada nas cinco últimas eleições —", 30,
                 "400", TINTA_FRACA))
    p.append(txt(L / 2, 572, "e não é garantia de acerto.", 30, "700", TINTA))

    # ---- o aviso, em tamanho que ninguém deixa de ler ----
    p.append(f'<rect x="60" y="632" width="{L - 120}" height="214" rx="12" '
             f'fill="{VERMELHO}"/>')
    p.append(txt(L / 2, 716, "ISTO NÃO É", 56, "700", PAPEL, esp="2"))
    p.append(txt(L / 2, 782, "RESULTADO OFICIAL", 56, "700", PAPEL, esp="2"))
    p.append(txt(L / 2, 822, "O resultado que vale é sempre o do TSE.", 27, "400",
                 PAPEL, op="0.92"))

    # ---- a tabela de erro ----
    p.append(txt(L / 2, 930, "Quanto o modelo errou nas últimas 5 eleições",
                 31, "700", TINTA))
    p.append(txt(L / 2, 972, "(em pontos percentuais)", 25, "400", TINTA_FRACA))

    topo = 1018
    alt = 74
    p.append(f'<rect x="72" y="{topo}" width="{L - 144}" height="{alt * 5 + 10}" '
             f'rx="12" fill="{PAPEL_2}"/>')
    p.append(txt(190, topo + 48, "APURADO", 24, "700", TINTA_FRACA, "middle", esp="2"))
    p.append(txt(610, topo + 48, "EM MÉDIA", 24, "700", TINTA_FRACA, "middle", esp="2"))
    p.append(txt(890, topo + 48, "PIOR CASO", 24, "700", TINTA_FRACA, "middle", esp="2"))
    for i, (marco, medio, pior) in enumerate(ERROS):
        y = topo + alt * (i + 1) + 50
        p.append(f'<rect x="100" y="{y - 52}" width="{L - 200}" height="2" '
                 f'fill="{TINTA}" opacity="0.12"/>')
        p.append(txt(190, y, marco, 36, "700", TINTA))
        p.append(txt(610, y, "± " + medio, 36, "700", VERDE))
        p.append(txt(890, y, "± " + pior, 36, "400", TINTA_FRACA))

    p.append(txt(L / 2, 1424, "Numa disputa decidida por menos que isso, a projeção",
                 27, "400", TINTA))
    p.append(txt(L / 2, 1462, "pode apontar o candidato errado no começo da noite.",
                 27, "400", TINTA))

    # ---- o que a página tem ----
    y = 1522
    p.append(f'<rect x="88" y="{y}" width="4" height="78" fill="{VERDE}"/>')
    p.append(txt(126, y + 32, "A APURAÇÃO", 24, "700", VERDE, "start", esp="3"))
    p.append(txt(126, y + 70, "Projeção ao vivo, ajustada a cada urna contada.",
                 28, "400", TINTA, "start"))

    y = 1628
    p.append(f'<rect x="88" y="{y}" width="4" height="118" fill="{VERMELHO}"/>')
    p.append(txt(126, y + 32, "AS PESQUISAS", 24, "700", VERMELHO, "start", esp="3"))
    p.append(txt(126, y + 70, "Sempre as mais recentes, com média ponderada por",
                 27, "400", TINTA, "start"))
    p.append(txt(126, y + 106, "pesquisa — atualizada assim que sai uma nova.",
                 27, "400", TINTA, "start"))

    # ---- faixa do link ----
    p.append(f'<rect x="0" y="1786" width="{L}" height="134" fill="{TINTA}"/>')
    p.append(txt(L / 2, 1843, ENDERECO, 35, "700", PAPEL))
    p.append(txt(L / 2, 1890, PERFIL, 25, "400", PAPEL, esp="2", op="0.8"))

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
