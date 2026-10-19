"""
Gera os ícones do app — os que ficam na tela de início do celular.

O desenho é o contorno real do Brasil (a mesma malha do IBGE que o site usa
no mapa), enchendo de baixo para cima.

A metáfora não é decorativa: a apuração acontece exatamente assim. Sul e
Centro-Oeste fecham primeiro, o Nordeste é o último a terminar, então a cor
subindo pelo mapa é literalmente o que acontece na noite de domingo. Quem
olha o ícone na tela de início entende o que o app faz sem precisar do nome.

A cor que sobe é verde, e isso é deliberado: no site inteiro, verde significa
"andamento da apuração" e nunca candidato. Um ícone em azul ou vermelho daria
a impressão de que o aplicativo torce por alguém, e é a última coisa que uma
ferramenta de projeção pode parecer. Nada de bandeira, número ou cor de
campanha.

Uso:  python3 gerar_icones.py
"""

from __future__ import annotations

import json
import os

import cairosvg

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

# Quanto do mapa já está "apurado" no desenho: o suficiente para a divisão
# ser evidente, sem parecer nem quase vazio nem quase cheio.
NIVEL = 0.56

FUNDO_1 = "#1C2438"
FUNDO_2 = "#0A0E17"
APURADO = "#34D399"      # verde: andamento, nunca candidato
APURADO_2 = "#10B981"
FALTA = "#38445F"
LINHA = "#A7F3D0"


def montar_svg(lado: int, area: float) -> str:
    """
    `area` é a fração do quadrado que o mapa ocupa. Nos ícones comuns ele
    pode ser generoso; no "maskable" o sistema recorta os cantos em círculo,
    então o desenho precisa caber no miolo.
    """
    with open(os.path.join(RAIZ, "mapa.json"), encoding="utf-8") as fh:
        mapa = json.load(fh)
    _, _, lmapa, amapa = (float(v) for v in mapa["viewBox"].split())

    escala = area * lado / max(lmapa, amapa)
    dx = (lado - lmapa * escala) / 2
    dy = (lado - amapa * escala) / 2
    r = lado * 0.22              # cantos: o sistema arredonda por cima

    # Onde fica a linha da água, em coordenadas do mapa.
    corte = 1 - NIVEL

    formas = "".join(
        '<path d="%s"/>' % d for d in mapa["ufs"].values()
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{lado}"
 height="{lado}" viewBox="0 0 {lado} {lado}">
<defs>
  <linearGradient id="ceu" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0" stop-color="{FUNDO_1}"/>
    <stop offset="1" stop-color="{FUNDO_2}"/>
  </linearGradient>
  <!-- Corte seco entre apurado e não apurado: dois pontos no mesmo lugar.
       Um degradê suave aqui pareceria sombra, não nível. -->
  <linearGradient id="nivel" x1="0" y1="0" x2="0" y2="1">
    <stop offset="{corte}" stop-color="{FALTA}"/>
    <stop offset="{corte}" stop-color="{APURADO}"/>
    <stop offset="1" stop-color="{APURADO_2}"/>
  </linearGradient>
  <!-- O mapa vira recorte: tudo que for pintado depois só aparece dentro
       do contorno do país. -->
  <clipPath id="brasil" clipPathUnits="userSpaceOnUse">
    <g transform="translate({dx:.2f},{dy:.2f}) scale({escala:.5f})">{formas}</g>
  </clipPath>
</defs>

<rect width="{lado}" height="{lado}" rx="{r:.1f}" fill="url(#ceu)"/>

<g clip-path="url(#brasil)">
  <rect x="0" y="0" width="{lado}" height="{lado}" fill="url(#nivel)"/>
  <!-- Risco claro na linha da água: dá o aspecto de medida, de marcação,
       e separa os dois tons mesmo num ícone de 48 pixels. -->
  <rect x="0" y="{lado * corte - lado * 0.012:.2f}" width="{lado}"
        height="{lado * 0.024:.2f}" fill="{LINHA}" opacity="0.92"/>
</g>
</svg>'''


def main() -> None:
    saidas = [
        ("icone-192.png", 192, 0.76),
        ("icone-512.png", 512, 0.76),
        # Android recorta este em círculo: o mapa precisa caber no miolo.
        ("icone-maskable.png", 512, 0.56),
        ("favicon.png", 64, 0.80),
    ]
    for nome, lado, area in saidas:
        svg = montar_svg(lado, area)
        caminho = os.path.join(RAIZ, nome)
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=caminho,
                         output_width=lado, output_height=lado)
        print("  %-26s %dx%d" % (nome, lado, lado))
    # Guarda o vetor, para quem quiser reaproveitar em outro tamanho.
    with open(os.path.join(RAIZ, "icone.svg"), "w", encoding="utf-8") as fh:
        fh.write(montar_svg(512, 0.76))
    print("  icone.svg")


if __name__ == "__main__":
    main()
