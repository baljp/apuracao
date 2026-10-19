#!/bin/sh
# Baixa os arquivos reais do 1º turno de 2026, renomeados com o código do 2º,
# para que os testes de resiliência rodem com dados verdadeiros em vez de
# dados inventados. Sem isso, um cenário de falha "passa" sem ter exercitado
# nada — que foi como a primeira versão destes testes se enganou.
cd "$(dirname "$0")" || exit 1
mkdir -p mock_1t && cd mock_1t || exit 1
B="https://resultados.tse.jus.br/oficial/ele2026/6257/dados"
for uf in ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz; do
  curl -sf "$B/$uf/$uf-c0001-e006257-u.json" -o "$uf-c0001-e006258-u.json"
  curl -sf "$B/$uf/$uf-e006257-ab.json"       -o "$uf-e006258-ab.json"
done
echo "$(ls | wc -l) arquivos em $(pwd)"
