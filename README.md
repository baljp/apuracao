# Projeção da apuração — Presidente 2026

Projeta o resultado final da eleição presidencial enquanto a apuração acontece,
a partir dos arquivos oficiais de divulgação do TSE.

**Site ao vivo:** https://baljp.github.io/apuracao-2026/

No backtest contra o 2º turno de 2022, com **5% apurado** a projeção errou
**0,24 ponto percentual**. O percentual bruto do TSE, no mesmo instante, estava
**9,4 pontos** fora.

---

## Por que o percentual bruto engana

Não é opinião, é geografia. Reconstruí a ordem real em que cada município
fechou a apuração no 1º turno de 2026 — os arquivos de andamento do TSE
registram o horário de totalização de cada um — e apliquei a ela os votos reais:

| Apurado | Nordeste na amostra | Candidato do PL aparecia com |
|---|---|---|
| 5% | **4%** | **64,3%** |
| 20% | 7% | 62,4% |
| 100% | **27%** | **51,0%** |

Com 5% apurado você estaria vendo um Brasil onde o Nordeste pesa 4% em vez de
27%. O número do TSE não está errado — é uma amostra enviesada pela ordem em que
os votos chegam. Sul e Centro-Oeste apuram rápido (municípios pequenos, poucas
seções); o Nordeste demora.

---

## Como o modelo funciona

Ele não tenta adivinhar o resultado. Mede o que mudou e aplica ao que falta.

**1. Esperado composicional.** Para cada um dos 5.716 municípios, o arquivo de
andamento do TSE diz quanto do eleitorado já foi totalizado. Somando município a
município, o modelo calcula *quanto a parcela já apurada teria dado no 1º turno*.
Se só o Sul apurou, o esperado também é só do Sul — é isso que anula o viés.

**2. Swing.** A diferença, em log-odds, entre o que saiu da urna e esse esperado.
O swing é o que de fato mudou entre os turnos: para onde foram os votos dos
eliminados, mudanças de comparecimento, humor do eleitorado. É uma quantidade
pequena e estável — muito mais fácil de estimar do que o resultado em si.

**3. Encolhimento hierárquico.** Com 1% apurado, o swing de um estado isolado é
ruído. Então ele é puxado para o da sua região, e o da região para o nacional,
com força inversa à informação disponível. No começo da noite o modelo é quase
nacional; conforme os votos entram, vira estadual. É isso que o deixa estável
desde cedo.

**4. Projeção e margem.** O que falta em cada município recebe a base do
município mais o swing que lhe cabe. A margem de 90% vem de um bootstrap que
perturba o swing, com a escala encolhendo conforme menos resta apurar.

A base é o **1º turno de 2026** — mesmos eleitores, mesmas seções, três semanas
antes. É uma referência bem melhor do que usar 2022.

O método é uma reconstrução independente da abordagem publicada por
[Rodrigo Mahlmeister](https://github.com/rodrigomahlmeister/apuracao-2026),
cujo modelo acertou o 1º turno de 2026.

---

## O backtest

Regra do jogo: base = 1º turno de 2022, alvo = 2º turno de 2022 (que o modelo
nunca vê), ordem de chegada = a ordem real observada no 1º turno de 2026.

| Apurado | Percentual bruto | Projeção do modelo |
|---|---|---|
| 1% | 58,15% (erro +9,05) | 49,07% (**erro −0,02**) |
| 3% | 58,68% (erro +9,58) | 48,86% (erro −0,24) |
| **5%** | 58,52% (erro +9,42) | **48,86% (erro −0,24)** |
| 10% | 58,33% (erro +9,23) | 48,95% (erro −0,15) |
| 20% | 58,15% (erro +9,06) | 49,03% (erro −0,06) |
| 50% | 54,52% (erro +5,43) | 49,19% (erro +0,09) |

Resultado real: Bolsonaro 49,10%. **Erro médio a partir de 5%: 0,07 pp. Erro
máximo: 0,24 pp.**

Duas ressalvas honestas:

- O teste é **mais difícil que a realidade**. Nele os municípios entram
  inteiros, enquanto na vida real as seções pingam de todo o país ao mesmo
  tempo. O viés que o modelo teve que vencer (+9,4 pp aos 5%) é maior que o real
  de 2022 (+4,2 pp, pelo histórico oficial do TSE).
- Os parâmetros foram calibrados nesse mesmo backtest, o que sempre favorece o
  resultado. A defesa é que o erro é praticamente idêntico em toda a grade de
  parâmetros testada (0,073 a 0,074 pp) — o modelo não depende de ajuste fino,
  que é o sintoma clássico de sobreajuste.

E a ressalva de fundo: 2026 pode não se comportar como 2022. O modelo supõe que
o swing entre turnos é geograficamente suave. Se houver uma reviravolta
concentrada numa região, ele vai demorar mais a perceber.

---

## O site

Não tem servidor, não tem banco de dados e não guarda nada. O TSE serve os
arquivos de divulgação com CORS liberado, então o navegador de quem está vendo
busca os dados direto na fonte oficial, e o modelo roda ali mesmo. Por isso
funciona hospedado em qualquer lugar estático e aguenta qualquer número de
visitantes.

Cada leitura são 27 arquivos de resultado + 27 de andamento, cerca de 700 KB
comprimidos, em torno de 1,5 segundo. O CDN do TSE revalida a cada 27 segundos
(`cache-control: max-age=27`), então o site lê a cada 30 — ler mais rápido só
gastaria banda sem trazer dado novo.

Para rodar localmente:

```bash
python3 -m http.server 8000     # na raiz do repositório
# abra http://localhost:8000
```

Adicione `?turno=1` à URL para acompanhar o 1º turno (útil para testar fora do
dia da eleição).

Conferência do modelo em JavaScript contra o resultado real:

```bash
node conferir.mjs
```

---

## O programa em Python (`programa/`)

Mesma lógica, para rodar na sua máquina com painel próprio:

```bash
cd programa
python3 apurador.py          # abre em localhost:8600
```

Sem dependências — só Python 3.

| Arquivo | O que faz |
|---|---|
| `apurador.py` | o programa: coleta, modelo e painel |
| `modelo.py` | o modelo de projeção |
| `tse.py` | endereços e leitura dos arquivos do TSE |
| `andamento.py` | quanto cada município já apurou |
| `baixar_base.py` | baixa o 1º turno de 2026 (roda uma vez) |
| `gerar_base_site.py` | gera o `base.json` enxuto do site |
| `preparar_2022.py` | monta o par 1º→2º turno de 2022 |
| `backtest.py` | roda a apuração de 2022 de novo e mede o erro |

Para refazer o backtest, baixe a [votação por seção de 2022](https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2022_BR.zip)
(271 MB) para `programa/dados2022/` e rode `preparar_2022.py` e depois
`backtest.py`.

---

## Fontes

- [TSE — divulgação de resultados](https://resultados.tse.jus.br)
- [TSE — informações técnicas sobre a divulgação](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados)
- [TSE Dados Abertos — resultados 2022](https://dadosabertos.tse.jus.br/dataset/resultados-2022)

---

## Importante

Isto é uma **estimativa estatística**, não um resultado oficial. O único
resultado válido é a totalização do TSE.

Se a projeção divergir do resultado final, significa que o modelo errou — nada
além disso. Modelos erram, e é para isso que serve a margem mostrada no site.
Diferença entre projeção e apuração não é evidência de problema na apuração.
