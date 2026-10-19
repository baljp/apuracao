# Projeção de apuração do 2º turno — descrição técnica para auditoria

Repositório: https://github.com/oxeeraassim/apuracao
Página: https://oxeeraassim.github.io/apuracao

Documento escrito para revisão crítica externa. A intenção é facilitar a
busca por erros, então ele inclui as limitações conhecidas e os resultados
negativos, não só o que funciona.

---

## 1. O problema

Durante a apuração, o percentual divulgado é a razão entre votos já contados.
Como as urnas não terminam de contar ao mesmo tempo em todo o país, esse
percentual é uma **amostra não aleatória**: é enviesada pela ordem de chegada.

Ordem de grandeza do viés, medida nos dados reais: com 5% do eleitorado
apurado, o Nordeste (27% do eleitorado nacional) costuma responder por ~4% do
que já foi contado. Nos backtests, o percentual bruto erra entre 8 e 12 pontos
percentuais nesse momento.

O objetivo do modelo não é prever o resultado do zero. É **corrigir o viés de
composição** da amostra parcial.

---

## 2. Dados de entrada

Todos públicos, lidos direto do TSE no navegador de quem acessa (sem servidor
intermediário):

| arquivo | conteúdo | uso |
|---|---|---|
| `{uf}-c0001-e{id}-u.json` | votos por candidato, por UF | votos observados |
| `{uf}-e{id}-ab.json` | andamento por município | fração já totalizada |

Base de referência: resultado do **1º turno de 2026 por município** (5.716
municípios), restrito aos dois finalistas, com o voto dos eliminados guardado
à parte (ver §3.4).

---

## 3. O modelo

### 3.1 Quantidade estimada

Para cada UF, define-se o **swing** em log-odds:

```
swing_uf = logit(obs_pl, obs_pt) − logit(esp_pl, esp_pt)
```

onde `esp_*` é o que a parcela **já apurada** teria produzido se cada município
repetisse exatamente seu 1º turno:

```python
for m in municipios_da_uf:
    s = share(m.base_logit)          # participação do PL na base daquele município
    v = m.fracao * m.validos_base    # quanto daquele município já foi apurado
    esp_pl += v * s
    esp_pt += v * (1 - s)
```

Ou seja: o modelo não estima "quem ganha". Estima **uma diferença** entre o
comportamento observado e uma base conhecida município a município — uma
quantidade pequena e estável. É daí que vem a estabilidade desde cedo.

### 3.2 Encolhimento hierárquico (nacional → região → UF)

Com 1% apurado, o swing de uma UF isolada é ruído. Média ponderada bayesiana
simples, com pesos em número de votos:

```python
def _encolher(valor, peso, prior, k):
    return (peso * valor + k * prior) / (peso + k)

K_UF     = 180_000.0   # votos
K_REGIAO =  90_000.0
```

Aplicação: swing nacional → prior da região; swing da região → prior da UF. No
início da noite o modelo é quase nacional; conforme os votos entram, vira
estadual. `MIN_VOTOS_SWING = 400` descarta UF com amostra desprezível.

### 3.3 Correção de voto válido (brancos, nulos, abstenção)

A projeção assume que o que falta rende o mesmo volume de voto válido do 1º
turno. Isso é falso entre turnos, e o desvio não é uniforme no país.

```python
escala_uf[uf] = votos_observados / votos_esperados   # mesma lógica do swing
# encolhida com o mesmo K_UF, limitada a [0.75, 1.25]
# aplicada ao volume do que falta:
v = falta * m.validos_base * fator
```

### 3.4 Perfil do município (voto dos eliminados)

O swing não é uniforme dentro de um estado: varia com a presença dos
candidatos eliminados no 1º turno. `perfil` = share dos eliminados no
município. Regressão ponderada e **regularizada** (`LAMBDA_PERFIL = 0.015`) do
swing estadual sobre o perfil, com 27 pontos — a regularização existe para
impedir o coeficiente de perseguir ruído.

### 3.5 Incerteza

Bootstrap de 240 amostras. O swing de cada UF é perturbado por um termo
**comum** a todas (erro nacional, que não some com mais apuração) e um termo
próprio, ambos encolhendo com a raiz do que falta:

```python
sigma = SIGMA_SWING * sqrt(frac_falta)     # SIGMA_SWING = 0.035
comum = gauss(0, sigma * 0.75)
ruido_uf = comum + gauss(0, sigma * 0.6)
```

A faixa publicada é o intervalo de 5%–95% das amostras. **Quando essa faixa
cruza 50%, a página não declara favorito** — diz que a diferença está dentro
da margem e que ainda não dá para saber.

---

## 4. Validação

### 4.1 Backtests em eleições reais

Metodologia: para cada ano, usa-se o 1º turno **daquele ano** como base, o
resultado real do 2º turno como alvo, e a ordem de chegada real observada em
2026. Erro absoluto da projeção, em pontos percentuais:

| apurado | média | pior caso |
|---|---|---|
| 5% | 0,96 | 1,83 (2014) |
| 20% | 0,73 | 1,57 (2018) |
| 50% | 0,30 | 0,79 |
| 75% | 0,14 | 0,43 |

Percentual bruto no mesmo ponto: ~9 pontos de erro aos 5%.

Anos: 2006, 2010, 2014, 2018, 2022. Comando: `python3 programa/backtest.py --ano N`

### 4.2 Eleições simuladas (1000 cenários)

Eleitorado real, resultado inventado **de propósito com as estruturas que o
modelo não pressupõe**: swing desigual entre regiões, swing dependente do
nível, choques estaduais, ruído município a município. Um gerador que
produzisse o que o modelo espera daria notas altas sem significar nada.

Acerto do vencedor:

| apurado | modelo | percentual bruto |
|---|---|---|
| 1% | 91,8% | 59,4% |
| 5% | **96,4%** | 59,4% |
| 20% | 98,1% | — |

Por aperto da disputa, aos 5% apurado:

| diferença final | acerto |
|---|---|
| > 2 pp | **100%** (814/814) |
| 1–2 pp | 92,3% |
| < 1 pp | 69,5% |

Erros graves (confiança > 95% no lado errado): **0 de 60**.

### 4.3 Paridade entre o modelo medido e o modelo publicado

A acurácia é medida em Python; o site roda JavaScript. `paridade.py` +
`paridade.mjs` comparam os dois em 11 pontos da apuração, com os mesmos dados
e num cenário com swing e comparecimento variando por região. Tolerâncias
configuradas em `paridade.mjs`: `TOL_PROJECAO = 1e-6` ponto percentual na
projeção nacional, `TOL_ESTADO = 1e-5` em cada estado, `TOL_MARGEM = 0.18` e
`TOL_PROB = 0.05` — margem e probabilidade com tolerância folgada porque saem
de 240 sorteios, que não são reprodutíveis entre as duas linguagens.

**Este teste existe porque a versão anterior dele só comparava com 100%
apurado** — ponto em que não sobra nada para projetar e qualquer modelo
acerta. Isso escondeu uma divergência real: o Python aplicava a correção de
voto válido (§3.3) e o JavaScript não. Os dois concordavam em 100% e divergiam
no meio da noite, que é quando a página é usada.

---

## 5. Limitações conhecidas

1. **Disputa abaixo de 1 ponto.** Aos 5% apurado o acerto cai para ~70%. É
   limite de informação, não de implementação. A página responde mostrando a
   margem e recusando-se a declarar favorito enquanto a diferença couber nela.

2. **Base de 4 anos.** Usar o 1º turno do mesmo ano é o caso favorável.
   Testado com base de 4 anos antes, o erro vai de 0,07 para 0,60–0,81 pp.
   Em 2026 a base é do 1º turno do mesmo ano.

3. **Apuração parcial dentro do município.** O TSE informa quanto do
   eleitorado foi totalizado, não quais seções. Se as seções que fecham
   primeiro votarem sistematicamente diferente das demais, há um viés interno
   invisível ao modelo. Testado em `simular_parcial.py` com divergência
   intramunicipal forte: erro de 0,36 pp.

4. **Dependência do `ab.json`.** O modelo precisa saber quanto falta. Se esse
   arquivo falhar e o de votos não, o modelo não tem o que corrigir. A página
   trata esse caso explicitamente (ver §6).

5. **Pesquisas (aba separada).** Vêm da Wikipédia, que qualquer um edita.
   Filtros de sanidade aplicados: amostra entre 100 e 500.000, data de campo
   não superior a hoje+1 dia, período dentro da janela do 2º turno. O texto é
   escapado antes de virar HTML.

## 6. Resultados negativos preservados

Documentados no repositório para não serem retentados:

- **Ancorar a projeção nas pesquisas**: ganho líquido zero.
- **Regressão sobre o nível** (`USAR_REGRESSAO_NIVEL = False`): pior em todas
  as 15 configurações testadas.
- **Calibrar parâmetros só em dados simulados**: escolheria valores que
  degradam 2018.
- **Ler o andamento com menos frequência** (economia de 95% de tráfego):
  custa 1,1–1,9 pp de erro entre 1% e 5% apurado. Descartado.

## 7. Defesas contra dado ruim

- UF com voto negativo, não finito, ou soma acima de 40 milhões é descartada.
- **Sem voto observado, não há placar.** Antes, se os votos falhassem e o
  andamento não, a página exibia "100% apurado · 50,0% × 50,0%" — um empate
  inventado com cara de resultado final.
- **Votos e andamento têm de chegar juntos.** Uma UF só entra no cálculo
  quando os DOIS arquivos dela responderam. Se só um chegar, o estado inteiro
  sai da conta e aparece no aviso de "estados sem resposta". Antes disso, se os
  votos de São Paulo chegassem e o andamento falhasse, os 22 milhões de votos
  entravam no total e o estado era projetado de novo por cima, como se nada
  tivesse sido apurado — **1,12 ponto percentual** de deslocamento na projeção
  nacional, medido. Defeito encontrado por auditoria externa e coberto agora
  por `programa/testar_desencontro.mjs`, que força os dois sentidos do
  descasamento.
- Com 20+ UFs sem resposta, a página diz que não conseguiu ler o TSE e não
  mostra número.
- Testado em 10 cenários de falha forçada: TSE fora, 404, JSON corrompido,
  JSON truncado, metade dos estados fora, votos absurdos, andamento acima de
  100%, TSE lento, Wikipédia fora.

---

## 8. O que eu pediria a um auditor

1. O encolhimento hierárquico com `K` fixo em votos é defensável, ou deveria
   ser função da variância observada entre UFs?
2. `SIGMA_SWING = 0.035` foi calibrado contra 2018/2022. A calibração
   (§4.2: 90% de cobertura observada em 300 disputas apertadas) é suficiente
   para sustentar a margem publicada?
3. O termo comum do bootstrap (0,75 do sigma) representa bem o erro nacional
   irredutível, ou subestima a cauda?
4. A correção de voto válido limitada a [0,75, 1,25] — o limite protege contra
   dado estranho ou mascara mudança real de comparecimento?
5. Há viés sistemático não coberto pelo gerador de cenários do §4.2?
