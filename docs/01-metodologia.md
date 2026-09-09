# 01. Metodologia

## Objetivo

Este projeto pega a infraestrutura AWS real do
[Projeto 04](https://github.com/amanda-martins-data/iac-pipeline-cloud-qualidade-ar)
(Lambda + S3 + RDS Postgres, provisionada via Terraform) e projeta
formalmente o que acontece com ela em 10x e 100x o volume de dados
atual - onde cada componente quebra, e quanto custaria em cada
patamar.

Diferente do [Blueprint (Projeto 09)](https://github.com/amanda-martins-data/blueprint-arquitetura-corporativa),
que desenhou requisitos nao-funcionais para um sistema novo e
fictício, aqui a base e infraestrutura que ja existe - a pergunta
nao e "como eu desenharia isso do zero", e "ate onde isso que ja
esta no ar aguenta, e o que fazer quando nao aguentar mais".

## Linha de base

O Projeto 04 processa dados de qualidade do ar para 3 cidades
(Sao Paulo, Rio de Janeiro, Belo Horizonte - os `DEFAULT_CITIES` do
pipeline), 5 poluentes por cidade (PM2.5, PM10, O3, NO2, CO), com
leitura horaria. Isso da:

```
3 cidades x 5 poluentes x 24 leituras/dia = 360 leituras/dia
```

Este numero (360) e a constante `readings_per_day(1)` no
[cost_model.py](../src/cost_model.py) - todo o resto do projeto e
esse numero multiplicado por 10 e por 100.

## Como os cenarios foram definidos

- **1x (linha de base)**: volume real e atual do Projeto 04.
- **10x**: cenario de crescimento moderado - mais cidades
  contratando o servico, sem mudanca de frequencia de leitura.
- **100x**: cenario de estresse, deliberadamente agressivo, para
  encontrar o ponto de ruptura com folga - nao e uma projecao de
  crescimento realista de curto prazo, e um teste dos limites do
  desenho atual.

## Metodologia de calculo do tempo de execucao da Lambda

A duracao de uma invocacao e modelada como:

```
duracao = overhead_fixo + leituras x (tempo_por_leitura + tempo_por_upsert)
```

- `overhead_fixo` (5s): cold start e setup de conexao com o RDS.
- `tempo_por_leitura` (0,05s): extracao, validacao e transformacao de
  uma leitura individual.
- `tempo_por_upsert` (0,005s): tempo de um `INSERT ... ON CONFLICT`
  individual no RDS - a arquitetura atual do Projeto 04 faz upsert
  linha a linha, nao em lote, o que e exatamente o que faz esse
  numero crescer linearmente com o volume (ver
  [02-pontos-de-ruptura.md](02-pontos-de-ruptura.md)).

Estes coeficientes sao estimativas de engenharia baseadas no
comportamento tipico de operacoes equivalentes (nao foram medidos
com profiling real em producao, ja que o volume de producao real
nunca chegou perto do ponto de ruptura) - o valor deste projeto esta
na metodologia e na logica de calculo, nao na precisao absoluta dos
coeficientes.

## Metodologia de custo

Os precos usados sao valores de referencia da AWS para a regiao
us-east-1, sem desconto de volume ou Savings Plan, com data de
referencia registrada explicitamente em `PRICING_REFERENCE_DATE`
(`src/cost_model.py`) - **precos de nuvem mudam**, e este modelo
existe para mostrar como a projecao de custo deveria ser feita, nao
para servir como cotacao valida indefinidamente. Qualquer uso real
deste modelo exigiria atualizar os precos contra a AWS Pricing
Calculator no momento do planejamento.

## Como reproduzir

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
python -c "from src.cost_model import build_scenario; print(build_scenario(10))"
```
