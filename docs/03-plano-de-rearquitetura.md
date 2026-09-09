# 03. Plano de Re-arquitetura

Este documento traduz os pontos de ruptura identificados em
[02-pontos-de-ruptura.md](02-pontos-de-ruptura.md) em acoes
concretas, ordenadas por prioridade - o que quebra primeiro, se
resolve primeiro. Nenhuma mudanca aqui e recomendada para
implementacao imediata: o achado central deste projeto e que **a
arquitetura atual do Projeto 04 aguenta o crescimento projetado sem
nenhuma mudanca** (ver secao "Quando agir", abaixo).

## Prioridade 1: Upsert em lote no RDS (resolve a causa raiz)

**Gatilho para implementar**: aproximacao do volume de 16.272
leituras/dia (45,2x a linha de base) - o ponto de ruptura exato
calculado em `cost_model.py`.

**Mudanca proposta**: substituir o upsert linha a linha
(`INSERT ... ON CONFLICT` individual, uma chamada por leitura) por
um upsert em lote, usando `INSERT ... ON CONFLICT` com multiplos
valores por statement (ou `COPY` para uma tabela temporaria seguido
de um unico `MERGE`/`UPSERT` em lote). Esta mudanca ataca
diretamente a causa raiz identificada no documento 02 - o termo
`tempo_por_upsert x leituras` que cresce linearmente - sem exigir
trocar nenhum componente da arquitetura.

**Por que e a prioridade 1, nao uma reescrita completa**: e a
mudanca de menor esforco que resolve o ponto de ruptura real. Trocar
o RDS por outro motor (proxima secao) resolveria o mesmo problema
com ordens de magnitude mais esforco de migracao - deveria ser
considerado apenas se o upsert em lote nao for suficiente.

## Prioridade 2: Dividir a Lambda em duas etapas (se o volume continuar crescendo alem do lote)

**Gatilho para implementar**: mesmo apos o upsert em lote, se o
volume continuar crescendo a ponto do tempo de *extracao e
transformacao* sozinho (sem contar o upsert) se aproximar do limite
de 900 segundos.

**Mudanca proposta**: separar a Lambda unica em duas etapas
orquestradas (ex.: Step Functions, ou duas tasks no mesmo DAG
Airflow se a orquestracao migrar para o padrao do
[Projeto 02](https://github.com/amanda-martins-data/orquestracao-airflow-qualidade-ar)):
uma Lambda de extracao/transformacao gravando na Silver, e uma
segunda Lambda (ou job) fazendo o load em lote para o RDS. Cada
etapa herda seu proprio limite de 900 segundos, dobrando a margem
antes do proximo ponto de ruptura.

## Prioridade 3: Motor de consulta alternativo para o RDS (cenario de longo prazo)

**Gatilho para implementar**: se o volume de leituras historicas
acumuladas tornar consultas analiticas sobre o RDS lentas (nao
coberto pelos testes deste projeto, que medem apenas tempo de
escrita/upsert, nao tempo de leitura analitica) - este e o mesmo
raciocinio de gatilho de motor de consulta descrito no
[documento 04 do Blueprint](https://github.com/amanda-martins-data/blueprint-arquitetura-corporativa/blob/main/04-modelo-fisico.md),
agora aplicado a infraestrutura real em vez de ao cenario fictício
da AeroWatch.

**Mudanca proposta**: nao substituir o RDS Postgres (ele continua
adequado para a carga transacional de upsert), mas replicar os dados
para um motor colunar otimizado para consulta analitica (ex.:
exportar periodicamente para Parquet no S3 e consultar via DuckDB ou
Athena, seguindo o mesmo padrao ja usado nos
[Projetos 01 e 03](https://github.com/amanda-martins-data/pipeline-qualidade-ar)),
em vez de forcar o RDS a fazer dois trabalhos diferentes
(transacional e analitico) igualmente bem.

## Quando agir: nenhuma mudanca e recomendada agora

O resultado mais importante deste projeto nao e a lista de mudancas
acima - e a conclusao de que **nenhuma delas e necessaria hoje**. O
cenario de 10x (crescimento moderado projetado) roda em 203 segundos,
menos de um quarto do limite de 900 segundos da Lambda, sem nenhuma
alteracao de codigo ou infraestrutura.

O Prioridade 1 (upsert em lote) e a unica mudanca que vale considerar
implementar de forma preventiva, nao porque o volume atual exige,
mas porque e uma mudanca de baixo risco e baixo esforco que empurra o
ponto de ruptura de 45,2x para muito alem do que qualquer cenario de
crescimento realista projeta - o tipo de melhoria que se faz quando
ha tempo de sobra, nao sob pressao de um incidente de producao.
