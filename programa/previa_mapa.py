"""
Gera uma imagem do mapa do jeito que ele aparece no site.

Serve para conferir o desenho sem depender de publicar e abrir o navegador, e
para comparar como o mapa se comporta no começo da noite (quase nada apurado)
e no fim.

Uso:
    python3 previa_mapa.py            prévias de 5% e de 100%
    python3 previa_mapa.py --pct 20   só a de 20%
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import modelo

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

FUNDO = "#ffffff"
CINZA = "#dfe3ea"      # estado sem urna contada
TEXTO = "#171a23"
FRACO = "#666d82"

# Estados pequenos demais para caber o rótulo dentro: o nome vai para uma
# coluna à direita, ligado por uma linha fina.
FORA = {
    "RN": (1095, 300), "PB": (1095, 360), "PE": (1095, 420),
    "AL": (1095, 480), "SE": (1095, 540),
    "DF": (1095, 640), "ES": (1095, 700), "RJ": (1095, 760),
}


def cor(pct_pl: float) -> str:
    """
    A cor diz quem lidera E por quanto: quanto mais longe dos 50%, mais
    escura. Isso antes estava embutido na opacidade, junto com o quanto já
    havia apurado — e o resultado era que um estado totalmente apurado mas
    disputado ficava pálido igual a um estado sem nenhuma urna contada. Duas
    informações diferentes não podem dividir o mesmo canal visual.
    """
    pl = pct_pl > 50
    margem = min(abs(pct_pl - 50) / 20.0, 1.0)   # satura em 20 pontos
    claro = (0xC4, 0xDA, 0xF0) if pl else (0xF4, 0xCD, 0xC9)
    forte = (0x1F, 0x5F, 0xA8) if pl else (0xB8, 0x2E, 0x24)
    return "#%02x%02x%02x" % tuple(
        round(c + (f - c) * margem) for c, f in zip(claro, forte))


def carregar():
    def ler(nome):
        with open(os.path.join(RAIZ, nome), encoding="utf-8") as fh:
            return json.load(fh)

    def ler_prog(nome):
        with open(os.path.join(AQUI, nome), encoding="utf-8") as fh:
            return json.load(fh)

    return (ler("mapa.json"), ler_prog("base_1t.json"), ler("base.json"),
            [o["chave"] for o in ler_prog("ordem_1t_2026.json")["ordem"]])


def estado_em(base_site, ordem, pct):
    idx = {base_site["ufs"][i] + "/" + base_site["cds"][i]: i
           for i in range(len(base_site["ufs"]))}
    limite = pct / 100.0 * sum(base_site["ele"])
    andamento, observado = {}, {}
    acc = 0.0
    for chave in ordem:
        if acc >= limite:
            break
        i = idx.get(chave)
        if i is None:
            continue
        andamento[chave] = 1.0
        uf = observado.setdefault(base_site["ufs"][i], {"pl": 0.0, "pt": 0.0})
        uf["pl"] += base_site["pl"][i]
        uf["pt"] += base_site["pt"][i]
        acc += base_site["ele"][i]
    return andamento, observado


def rotulo(x, y, texto, tamanho, peso="700", cor_txt="#ffffff", sombra=True):
    # Sombra leve por baixo em vez de contorno grosso: o contorno engrossa
    # tanto a letra que ela perde a cor de dentro e parece cinza.
    s = ""
    if sombra:
        s += ('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="'
              'Helvetica,Arial" font-size="%d" font-weight="%s" fill="rgba(0,0,0,.33)"'
              '>%s</text>' % (x + 1.2, y + 1.2, tamanho, peso, texto))
    s += ('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="'
          'Helvetica,Arial" font-size="%d" font-weight="%s" fill="%s">%s</text>'
          % (x, y, tamanho, peso, cor_txt, texto))
    return s


def desenhar(mapa, r, nome_pl, nome_pt, caminho):
    por_uf = {e["uf"]: e for e in r["estados"]}
    vb = mapa["viewBox"].split()
    largura, altura = float(vb[2]), float(vb[3])
    largura_total = largura + 190   # espaço para a coluna de rótulos externos
    topo = 100

    p = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" '
         'width="%.0f" height="%.0f">'
         % (largura_total, altura + topo, largura_total * 0.66,
            (altura + topo) * 0.66),
         '<rect width="100%%" height="100%%" fill="%s"/>' % FUNDO,
         '<text x="24" y="44" font-family="Helvetica,Arial" font-size="35" '
         'font-weight="700" fill="%s">Mapa da apuração</text>' % TEXTO,
         '<text x="24" y="80" font-family="Helvetica,Arial" font-size="25" '
         'fill="%s">%s%% apurado · projeção %s %s%% × %s%% %s</text>'
         % (FRACO, ("%.1f" % r["pct_apurado"]).replace(".", ","), nome_pl,
            ("%.1f" % r["projecao_pl"]).replace(".", ","),
            ("%.1f" % r["projecao_pt"]).replace(".", ","), nome_pt),
         '<g transform="translate(0,%d)">' % topo]

    # 1. formas
    for uf, d in mapa["ufs"].items():
        e = por_uf.get(uf)
        apu = max(0.0, min(e["pct_apurado"], 100.0)) if e else 0.0
        if apu < 1:
            # Sem urna contada: cinza e contorno tracejado. Fica claro que
            # ali não há dado, em vez de parecer uma cor fraca.
            p.append('<path d="%s" fill="%s" stroke="#b9c0cc" '
                     'stroke-width="2" stroke-dasharray="7 5" '
                     'stroke-linejoin="round"/>' % (d, CINZA))
        else:
            # A opacidade agora carrega UMA informação só: o quanto apurou.
            opac = 0.45 + 0.55 * (apu / 100.0)
            p.append('<path d="%s" fill="%s" fill-opacity="%.2f" stroke="%s" '
                     'stroke-width="2.5" stroke-linejoin="round"/>'
                     % (d, cor(e["proj_pl"]), opac, FUNDO))

    # 2. rótulos dentro dos estados grandes
    for uf, pos in mapa["rotulos"].items():
        e = por_uf.get(uf)
        if not e or uf in FORA:
            continue
        apu = e["pct_apurado"]
        if apu < 1:
            p.append(rotulo(pos[0], pos[1], uf, 25, cor_txt=FRACO, sombra=False))
            continue
        p.append(rotulo(pos[0], pos[1] - 4, uf, 27))
        p.append(rotulo(pos[0], pos[1] + 21,
                        ("%.1f" % e["proj_pl"]).replace(".", ",") + "%", 22, "600"))

    # 3. rótulos fora, para os estados pequenos
    for uf, (lx, ly) in FORA.items():
        e = por_uf.get(uf)
        pos = mapa["rotulos"].get(uf)
        if not e or not pos:
            continue
        apu = e["pct_apurado"]
        c = cor(e["proj_pl"]) if apu >= 1 else "#aab2c0"
        p.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                 'stroke-width="1.6" opacity=".55"/>'
                 % (pos[0], pos[1], lx - 100, ly - 7, c))
        p.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>'
                 % (pos[0], pos[1], c))
        p.append('<rect x="%.1f" y="%.1f" width="96" height="30" rx="6" '
                 'fill="%s"/>' % (lx - 96, ly - 22, c))
        p.append('<text x="%.1f" y="%.1f" font-family="Helvetica,Arial" '
                 'font-size="19" font-weight="700" fill="#fff">%s</text>'
                 % (lx - 89, ly, uf))
        p.append('<text x="%.1f" y="%.1f" font-family="Helvetica,Arial" '
                 'font-size="18" font-weight="600" fill="#fff" '
                 'text-anchor="end">%s</text>'
                 % (lx - 6, ly, ("%.0f" % e["proj_pl"]).replace(".", ",") + "%"
                    if apu >= 1 else "—"))

    p.append("</g></svg>")
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write("".join(p))
    return caminho


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pct", type=float, default=None)
    args = ap.parse_args()

    mapa, base, base_site, ordem = carregar()
    mdl = modelo.Modelo(base)
    nomes = base_site.get("nomes", {})
    nome_pl = (nomes.get("pl") or "PL").split()[0].title()
    nome_pt = (nomes.get("pt") or "PT").split()[0].title()

    for pct in ([args.pct] if args.pct is not None else [5, 100]):
        andamento, observado = estado_em(base_site, ordem, pct)
        r = mdl.projetar(andamento, observado, n_bootstrap=0)
        nome = os.path.join(RAIZ, "previa-mapa-%g.svg" % pct)
        desenhar(mapa, r, nome_pl, nome_pt, nome)
        print("  %5.1f%% apurado -> %s  (projeção %.2f%%)"
              % (r["pct_apurado"], os.path.basename(nome), r["projecao_pl"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
