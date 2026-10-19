"""
Gera os ícones do app (os que aparecem na tela de início do celular).

O desenho é propositalmente neutro: uma barra dividida, que é o próprio placar
da projeção. Nada de símbolo partidário, bandeira ou cor de campanha — o ícone
não deve parecer propaganda de nenhum dos lados.

Uso:  python3 gerar_icones.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

FUNDO = (15, 17, 23)
AZUL = (74, 144, 217)
VERMELHO = (217, 84, 74)
TRILHO = (39, 43, 56)
CLARO = (233, 235, 242)


def desenhar(tamanho: int, margem_externa: bool = False) -> Image.Image:
    img = Image.new("RGBA", (tamanho, tamanho), FUNDO + (255,))
    d = ImageDraw.Draw(img)
    u = tamanho / 100.0

    # Em telas que recortam o ícone em círculo (Android), o conteúdo precisa
    # caber na área central segura.
    pad = 26 if margem_externa else 16

    largura = tamanho - 2 * pad * u
    x0 = pad * u
    altura = 11 * u
    raio = altura / 2

    # Três barras: as duas de cima são o placar, a de baixo é a apuração.
    linhas = [
        (34, 0.52, AZUL, VERMELHO),
        (50, 0.46, AZUL, VERMELHO),
    ]
    for y_pct, corte, esq, dir_ in linhas:
        y = y_pct * u
        d.rounded_rectangle([x0, y, x0 + largura, y + altura], raio, fill=dir_)
        d.rounded_rectangle([x0, y, x0 + largura * corte, y + altura], raio, fill=esq)

    # Barra de andamento, parcialmente preenchida.
    y = 66 * u
    d.rounded_rectangle([x0, y, x0 + largura, y + altura], raio, fill=TRILHO)
    d.rounded_rectangle([x0, y, x0 + largura * 0.3, y + altura], raio, fill=(73, 201, 138))

    # Marca dos 50%, que é o que decide a eleição.
    meio = x0 + largura / 2
    d.rounded_rectangle(
        [meio - 1.2 * u, 26 * u, meio + 1.2 * u, 63 * u], 1.2 * u, fill=CLARO
    )
    return img


def main() -> None:
    for tamanho in (192, 512):
        desenhar(tamanho).save(os.path.join(RAIZ, "icone-%d.png" % tamanho))
        print("icone-%d.png" % tamanho)
    # Versão com margem extra, para recorte circular no Android.
    desenhar(512, margem_externa=True).save(os.path.join(RAIZ, "icone-maskable.png"))
    print("icone-maskable.png")
    # Favicon.
    desenhar(64).save(os.path.join(RAIZ, "favicon.png"))
    print("favicon.png")


if __name__ == "__main__":
    main()
