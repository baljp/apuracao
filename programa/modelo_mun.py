"""
Variante EXPERIMENTAL do modelo: o swing deixa de ser só por estado e passa a
depender de características de cada município, aprendidas com os municípios
que já fecharam.

Ideia (a que o João propôs): olhar como cada município votou no 1º turno,
comparar com como ele votou no 2º à medida que as urnas saem, e usar isso para
ajustar o que falta. Um município que ainda não fechou não tem dado próprio,
então a informação vem dos parecidos: cidades onde o candidato era mais forte,
com mais voto de terceiros, ou maiores, se moveram diferente das outras DENTRO
do mesmo estado?

Diferença para o modelo atual: lá, a regressão sobre o perfil usa os 27 pontos
(estados). Aqui usa milhares de municípios, comparando cada um com os da
mesma UF, o que tira o viés de composição que derrubou a regressão por nível
estadual (ver modelo.py, USAR_REGRESSAO_NIVEL).

Fica fora do site até provar, nos testes, que melhora.
"""

from __future__ import annotations

import math

import modelo

# Parâmetros (ajustados em comparar_mun.py).
TAU = 0.06          # heterogeneidade própria de cada município, em log-odds
LAMBDA_MUN = 0.5    # regularização, relativa ao peso total
LIMITE_MUN = 0.20   # teto do ajuste por município, em log-odds
MIN_MUN_UF = 3      # municípios fechados na UF para ela entrar na regressão
USAR = ("nivel", "perfil", "tamanho")


class ModeloMun(modelo.Modelo):
    def __init__(self, base):
        super().__init__(base)
        ms = self.municipios
        peso = sum(m.validos_base for m in ms) or 1.0
        self._cov = {}
        for m in ms:
            self._cov[m.chave] = self._covariaveis(m)
        # Desvio-padrão global de cada covariável, para pôr todas na mesma régua.
        n = len(USAR)
        self._sd = []
        for k in range(n):
            mu = sum(self._cov[m.chave][k] * m.validos_base for m in ms) / peso
            var = sum(((self._cov[m.chave][k] - mu) ** 2) * m.validos_base
                      for m in ms) / peso
            self._sd.append(math.sqrt(var) or 1.0)
        for m in ms:
            self._cov[m.chave] = [v / s for v, s in zip(self._cov[m.chave], self._sd)]
        self._obs_mun = None
        self._b = None
        self._xbar = {}

    def _covariaveis(self, m):
        x = []
        if "nivel" in USAR:
            x.append(m.base_logit - self.nivel_uf.get(m.uf, 0.0))
        if "perfil" in USAR:
            x.append(m.perfil)
        if "tamanho" in USAR:
            x.append(math.log(max(m.validos_base, 1.0)))
        return x

    # ------------------------------------------------------------------
    def projetar(self, andamento, observado, obs_mun=None, **kw):
        self._obs_mun = obs_mun
        self._b = None
        self._xbar = {}
        return super().projetar(andamento, observado, **kw)

    def _coef_perfil(self, swing_uf, peso_uf):
        """Aproveita o gancho do modelo base para ajustar a regressão por
        município; o coeficiente por estado deixa de ser usado."""
        self._ajustar()
        return 0.0

    def _ajustar(self):
        if not self._obs_mun:
            return
        k = len(USAR)
        por_uf = {}
        for chave, (pl, pt) in self._obs_mun.items():
            m = self.por_chave.get(chave)
            n = pl + pt
            if m is None or n < 50 or pl <= 0 or pt <= 0:
                continue
            e = modelo._logit(pl, pt) - m.base_logit
            w = 1.0 / (4.0 / n + TAU * TAU)
            por_uf.setdefault(m.uf, []).append((self._cov[chave], e, w))

        xtx = [[0.0] * k for _ in range(k)]
        xty = [0.0] * k
        peso_total = 0.0
        for uf, itens in por_uf.items():
            if len(itens) < MIN_MUN_UF:
                continue
            sw = sum(w for _, _, w in itens)
            xbar = [sum(x[j] * w for x, _, w in itens) / sw for j in range(k)]
            ebar = sum(e * w for _, e, w in itens) / sw
            self._xbar[uf] = xbar
            for x, e, w in itens:
                dx = [x[j] - xbar[j] for j in range(k)]
                de = e - ebar
                for a in range(k):
                    xty[a] += w * dx[a] * de
                    for b in range(k):
                        xtx[a][b] += w * dx[a] * dx[b]
                peso_total += w
        if peso_total <= 0:
            return
        for a in range(k):
            xtx[a][a] += LAMBDA_MUN * peso_total * 0.01
        self._b = _resolver(xtx, xty)

    # ------------------------------------------------------------------
    def _somar(self, swing_final, observado, ruido=None, b_perfil=0.0, escala=None):
        if self._b is None:
            return super()._somar(swing_final, observado, ruido, b_perfil, escala)

        total_pl = total_pt = 0.0
        por_uf = {}
        k = len(USAR)
        for uf, muns in self.por_uf.items():
            obs = observado.get(uf) or {}
            pl = float(obs.get("pl", 0))
            pt = float(obs.get("pt", 0))
            sw = swing_final.get(uf, 0.0)
            if ruido:
                sw += ruido.get(uf, 0.0)
            xbar = self._xbar.get(uf)
            fator = (escala or {}).get(uf, 1.0)
            for m in muns:
                falta = 1.0 - m.fracao
                if falta <= 1e-9:
                    continue
                sw_m = sw
                if xbar is not None:
                    x = self._cov[m.chave]
                    aj = sum(self._b[j] * (x[j] - xbar[j]) for j in range(k))
                    sw_m += max(-LIMITE_MUN, min(LIMITE_MUN, aj))
                s = modelo._share(m.base_logit + sw_m)
                v = falta * m.validos_base * fator
                pl += v * s
                pt += v * (1.0 - s)
            soma = pl + pt
            por_uf[uf] = {"pl": pl, "pt": pt,
                          "pct_pl": 100.0 * pl / soma if soma else 50.0}
            total_pl += pl
            total_pt += pt
        soma = total_pl + total_pt
        return {"pl": total_pl, "pt": total_pt,
                "pct_pl": 100.0 * total_pl / soma if soma else 50.0,
                "por_uf": por_uf}


def _resolver(a, b):
    """Gauss-Jordan para sistemas pequenos."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(m[r][i]))
        if abs(m[p][i]) < 1e-12:
            return [0.0] * n
        m[i], m[p] = m[p], m[i]
        for r in range(n):
            if r != i:
                f = m[r][i] / m[i][i]
                for c in range(i, n + 1):
                    m[r][c] -= f * m[i][c]
    return [m[i][n] / m[i][i] for i in range(n)]
