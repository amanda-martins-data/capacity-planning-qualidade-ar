# 02. Pontos de Ruptura

Analise componente por componente da infraestrutura do
[Projeto 04](https://github.com/amanda-martins-data/iac-pipeline-cloud-qualidade-ar),
com os numeros exatos calculados por [`cost_model.py`](../src/cost_model.py)
e verificados pelos testes em [`tests/test_cost_model.py`](../tests/test_cost_model.py).

## Resumo dos tres cenarios

| Cenario | Leituras/dia | Duracao da Lambda | Excede timeout (900s)? | Custo total/mes |
|---|---|---|---|---|
| 1x (linha de base real) | 360 | 24,8s | Nao | $14,60 |
| 10x (crescimento projetado) | 3.600 | 203,0s | Nao | $15,11 |
| 100x (cenario de estresse) | 36.000 | 1.985,0s | **Sim** | $20,20 |

## Lambda: o unico componente que efetivamente quebra

**Ponto de ruptura exato**: 16.272 leituras/dia, equivalente a
**45,2x** a linha de base - calculado algebricamente por
`find_lambda_timeout_breakpoint()`, nao estimado por tentativa e
erro.

A causa raiz nao e o volume em si, e uma decisao de implementacao do
Projeto 04: o upsert no RDS e feito **linha a linha**
(`INSERT ... ON CONFLICT` individual), nao em lote. Isso faz o tempo
de execucao crescer linearmente com o numero de leituras sem
nenhuma otimizacao de I/O - e exatamente o tipo de decisao que
parecia irrelevante na escala original (360 leituras/dia, 24,8
segundos de execucao) e se torna o fator limitante em escala.

**Achado importante**: o cenario de 10x - o crescimento realista
projetado para os proximos meses, nao o cenario de estresse - roda
em 203 segundos, bem dentro do limite de 900 segundos. **Isso
significa que a arquitetura atual do Projeto 04 nao precisa de
nenhuma mudanca para suportar o crescimento projetado de curto
prazo.** O ponto de ruptura so aparece no cenario de estresse
deliberadamente agressivo (100x), nao em nenhum horizonte de
planejamento realista.

## S3: cresce, mas nunca vira o custo dominante

O custo do S3 cresce de forma proporcional ao volume, mas nao
apresenta nenhum limite tecnico de escala (ao contrario da Lambda).
O achado real, verificado pelo teste
`test_s3_cost_grows_but_never_becomes_the_dominant_cost`, e a
mudanca de proporcao no orcamento total:

| Cenario | Custo S3/mes | % do custo total |
|---|---|---|
| 1x | $0,05 | 0,4% |
| 10x | $0,54 | 3,6% |
| 100x | $5,41 | 26,8% |

Aos 100x, o S3 deixa de ser irrelevante (era a suposicao inicial
antes de rodar os numeros) e passa a ser quase um terco do custo
total - mas mesmo assim continua abaixo do custo fixo do RDS em
todos os cenarios testados. Nao ha gatilho de reprojeto aqui, so um
alerta de que a composicao do custo muda com a escala.

## RDS: custo fixo, gatilho e desempenho, nao preco

O custo mensal do RDS (`$14,54` em todos os tres cenarios) e
constante porque modela uma instancia `db.t3.micro` ligada o mes
inteiro, independente do volume processado - a instancia nao
"desliga" entre execucoes diarias da Lambda.

Isso significa que o RDS **nao tem um gatilho de custo** ligado ao
volume de leituras, mas tem um gatilho de **desempenho**: e o
upsert linha a linha no RDS que, combinado ao tempo de
transformacao, causa o estouro do timeout da Lambda descrito acima.
O RDS em si nao quebra - o jeito como ele e usado pela Lambda que
quebra.

## VPC Endpoints ([ADR 0004](https://github.com/amanda-martins-data/adr-arquitetura-dados/blob/main/decisions/0004-nat-gateway-vs-vpc-endpoints.md)): decisao que permanece valida em qualquer escala

A decisao de usar VPC Endpoints (Gateway gratuito para S3, Interface
de baixo custo para Secrets Manager) em vez de NAT Gateway foi
tomada no Projeto 04 comparando custo fixo por hora. Essa comparacao
**nao muda com o volume de leituras**: o Gateway Endpoint para S3
continua gratuito independente de quantos objetos sao gravados, e o
trafego para Secrets Manager (leitura de credencial) nao cresce com
o volume de dados processados - e uma chamada por invocacao,
nao uma chamada por leitura.

Vale destacar isso explicitamente: nem toda decisao de arquitetura
precisa ser revisitada quando o volume cresce. Esta e uma delas que
permanece correta em qualquer um dos tres cenarios testados.

## O que nao foi modelado (limitacoes explicitas)

- Concorrencia de multiplas invocacoes simultaneas da Lambda (o
  Projeto 04 roda uma execucao diaria, entao isso nao e um risco no
  desenho atual).
- Limite de conexoes do RDS (`max_connections`) - irrelevante
  enquanto houver apenas uma invocacao por dia; se o pipeline
  passasse a rodar com concorrencia (ex.: um Lambda por cidade em
  paralelo), este seria um proximo ponto a modelar.
- Custo de transferencia de dados entre regioes ou para fora da AWS
  - o pipeline atual opera inteiramente dentro da mesma regiao.
