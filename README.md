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

## 50 eleições cegas

Duas eleições reais são pouca coisa para saber onde um modelo quebra. Então o
`programa/simular.py` inventa dezenas de resultados sobre os municípios reais —
o eleitorado e o voto do 1º turno de 2026 são verdadeiros, o 2º turno é
sorteado — e usa a ordem de chegada real.

Os cenários são gerados de propósito com as estruturas que o modelo **não**
pressupõe: swing desigual entre regiões, swing que depende do nível do lugar,
choque em um estado sorteado e ruído município a município. Um gerador que
produzisse o que o modelo espera daria notas altas sem significar nada.

| Apurado | Projeção (médio / p90 / pior) | Percentual bruto (médio / pior) |
|---|---|---|
| 0,5% | 1,01 / 2,12 / 2,69 pp | 14,65 / 17,72 pp |
| 1% | 0,55 / 1,09 / 1,51 pp | 12,88 / 15,26 pp |
| **5%** | **0,34 / 0,71 / 1,15 pp** | 12,97 / 14,80 pp |
| 10% | 0,26 / 0,47 / 0,85 pp | 11,77 / 13,38 pp |
| 50% | 0,16 / 0,37 / 0,52 pp | 6,72 / 7,77 pp |

**Com 5% apurado o modelo apontou o vencedor certo em 49 das 50.** O percentual
bruto acertaria 32.

O erro cresce conforme o país se move de forma mais desigual — 0,20 pp quando
as regiões andam juntas, 0,44 pp quando se espalham. É o mesmo mecanismo que
explica 2018.

**Duas ressalvas.** Nos cenários parecidos com 2018 o modelo erra 0,29 pp, mas
em 2018 de verdade errou 1,79 pp: o gerador ainda não é tão cruel quanto a
realidade, porque nele o swing regional é sorteado de forma independente,
enquanto em 2018 ele estava correlacionado com a ordem em que os estados
apuraram. Trate a simulação como o melhor caso e 2018 como o pior.

E a simulação **não** foi usada para calibrar. Os parâmetros que ela escolhe
(`K_UF=60000, K_REGIAO=30000`) melhoram 38% nos cenários inventados e pioram em
2018 — o ganho vem de decorar o gerador. O `calibrar_simulado.py` confere
sempre contra as eleições reais justamente para pegar isso.

---

## Experimentos que não deram certo

Ficam registrados porque economizam o tempo de quem tiver a mesma ideia.

**Ancorar o swing nas pesquisas finais** (como faz o modelo do Mahlmeister).
Testado com as pesquisas reais de cada ano: melhora 0,39 pp em 2018 com 1%
apurado, piora 0,24 pp em 2022, some a partir de 3%. Balanço zero. Revelador:
em 2018 a âncora estava quase perfeita (dava 55,0%, real foi 55,13%) e mesmo
assim o erro de +1,8 pp persistiu — prova de que o problema de 2018 não é o
nível nacional, e sim a distribuição regional.

**Regressão do swing sobre o nível do lugar.** Em 2018 a relação é forte (onde
o candidato era forte caiu mais), e a inclinação medida com tudo apurado é
−0,140. Mas no início da noite ela não é mensurável: os estados que apuram
primeiro são os de nível alto, e a parcela apurada deles ainda não os
representa. Testado em 15 combinações, piora em todas. Veja
`programa/testar_nivel.py`.

---

## Quão difícil deve ser 2026

Os dois backtests dão erros muito diferentes — 0,24 pp em 2022 e 1,79 pp em
2018 — e a diferença não é acaso. Ela tem uma causa mensurável antes da
apuração começar: **quanto voto sobrou dos candidatos eliminados**.

| Eleição | Finalistas somavam no 1º turno | Voto a redistribuir | Erro aos 5% |
|---|---|---|---|
| 2018 | 75,31% (46,03 + 29,28) | **24,7%** | 1,79 pp |
| 2022 | 91,63% (43,20 + 48,43) | 8,4% | 0,24 pp |
| **2026** | **92,19%** (47,03 + 45,16) | **7,8%** | ? |

Quanto mais voto ficou solto, mais o eleitorado precisa se reorganizar entre os
turnos — e essa reorganização é geograficamente desigual, que é exatamente o
que o modelo não consegue antecipar. Em 2018, um quarto do eleitorado teve de
escolher de novo; em 2026, menos de um décimo.

Pelo indicador, **2026 é o cenário mais favorável dos três**, um pouco melhor
até que 2022. Não é garantia: é um indicador estrutural, e uma reviravolta
concentrada numa região continuaria sendo invisível para o modelo até aquela
região apurar.

---

## O quanto a base recente importa

`programa/backtest_pares.py` testa o modelo com bases de anos anteriores, para
medir o quanto ele depende de a base ser fresca. Em todos, a ordem de chegada
é a real de 2026.

| Par | Distância | Erro médio aos 5% | Pior |
|---|---|---|---|
| 1º turno 2022 → 1º turno 2026 | 4 anos, com troca de candidato | 0,81 pp | 2,32 pp |
| 2º turno 2018 → 2º turno 2022 | 4 anos | 0,60 pp | 1,18 pp |
| 1º turno 2022 → **2º turno 2022** | 3 semanas | **0,07 pp** | 0,24 pp |

Mesmo prevendo quatro anos à frente, e mesmo com o candidato trocando
(Bolsonaro saiu, Flávio entrou), o erro fica abaixo de 1 ponto — enquanto o
percentual bruto erraria 11,6 pontos no mesmo instante. Isso mostra que o
modelo se apoia na geografia do voto, que é estável.

Mas a base de três semanas é dez vezes melhor que a de quatro anos. É por isso
que este projeto usa o 1º turno de 2026 como base, e não 2022.

Um detalhe que contraria a intuição: prever o 2º turno de 2022 a partir do 2º
turno de **2018** (0,60 pp) saiu melhor que prevê-lo a partir do 1º turno do
próprio 2022 em 2018 (1,10 pp). Dois segundos turnos se parecem entre si mais
do que um primeiro e um segundo turno do mesmo ano, porque no segundo turno a
disputa já está reorganizada em dois blocos.

---

## Três formas de usar

**1. Site.** https://baljp.github.io/apuracao-2026/ — abre em qualquer
navegador, nada para instalar.

**2. Como aplicativo no celular.** Abra o site e toque em **Instalar** (no
Android) ou em **Compartilhar → Adicionar à Tela de Início** (no iPhone). Vira
um ícone na tela inicial e abre em tela cheia, sem barra de navegador. A página
fica guardada no aparelho, então abre na hora mesmo com internet ruim — mas os
dados do TSE nunca são guardados em cache, para nunca mostrar número velho.

**3. Arquivo único.** O [`apuracao.html`](apuracao.html) tem tudo dentro dele —
página, modelo e a base dos 5.716 municípios, em 298 KB. Dá para salvar no
celular, mandar por WhatsApp ou levar num pendrive. Abre direto, sem servidor.
Funciona porque o TSE libera CORS até para origem nula, que é o caso de um
arquivo aberto do próprio aparelho. Só precisa de internet na hora de buscar os
dados, que é o ponto.

Para regerar o arquivo único depois de mexer no site:
`python3 programa/gerar_html_unico.py`

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
