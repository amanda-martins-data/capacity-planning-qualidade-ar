# Revisao de Escalabilidade e Custo (Capacity Planning)

Analise formal de capacidade e custo da infraestrutura AWS real do
[Projeto 04](https://github.com/amanda-martins-data/iac-pipeline-cloud-qualidade-ar)
(Lambda + S3 + RDS Postgres) - onde cada componente quebra conforme
o volume de dados cresce 10x e 100x, quanto custaria em cada
patamar, e um plano de re-arquitetura priorizado para quando o
gatilho de ruptura for atingido.

Projeto 10 de uma serie documentando minha transicao de Analista de
Dados para Arquitetura de Dados - veja o [perfil
completo](https://github.com/amanda-martins-data).

## Por que este projeto e diferente do Blueprint (Projeto 09)

O [Blueprint de Arquitetura Corporativa](https://github.com/amanda-martins-data/blueprint-arquitetura-corporativa)
desenhou requisitos nao-funcionais para um sistema **novo e
fictício**, do zero. Este projeto faz o caminho inverso: pega
infraestrutura **que ja existe e ja foi provisionada de verdade**
(Projeto 04) e pergunta "ate onde isso aguenta, e o que fazer quando
nao aguentar mais" - com um modelo de custo real, testado, nao
apenas documentado em prosa.

## O achado central

O ponto de ruptura da Lambda (excede o limite de 900 segundos de
execucao) acontece em **16.272 leituras/dia, 45,2x a linha de
base real** - calculado algebricamente, nao estimado. O cenario de
crescimento projetado (10x) roda em 203 segundos, um quarto do
limite - **a arquitetura atual nao precisa de nenhuma mudanca para
suportar o crescimento realista de curto prazo**. Detalhes completos
em [docs/02-pontos-de-ruptura.md](docs/02-pontos-de-ruptura.md).

## Estrutura

```
.
├── docs/
│   ├── 01-metodologia.md              # como a projecao foi calculada
│   ├── 02-pontos-de-ruptura.md        # onde cada componente quebra, com numeros exatos
│   └── 03-plano-de-rearquitetura.md   # o que fazer, em que ordem, e quando agir
├── src/
│   └── cost_model.py                  # modelo de custo e capacidade, parametrizado por volume
└── tests/
    └── test_cost_model.py             # 14 testes garantindo que os numeros documentados batem com o codigo
```

## Como rodar

```bash
pip install -r requirements.txt

# rodar os 14 testes
python -m pytest tests/ -v

# calcular um cenario especifico
python -c "from src.cost_model import build_scenario; print(build_scenario(10))"
```

## Validacao

**14/14 testes passando**, incluindo:
- Confirmacao de que o ponto de ruptura calculado (45,2x) bate com o
  numero documentado em `02-pontos-de-ruptura.md` - se o codigo
  mudar, o teste falha e avisa que a documentacao ficou desatualizada.
- Cenarios logo abaixo e logo acima do breakpoint, confirmando a
  transicao exata.
- Confirmacao de que o cenario de 10x (crescimento realista) nao
  excede o limite da Lambda.
- Verificacao de que o S3 cresce em proporcao do custo total, mas
  nunca ultrapassa o custo fixo do RDS nos cenarios testados.

## Metodologia e precos

Todos os precos de referencia (AWS us-east-1, sem desconto de
volume) tem data registrada explicitamente no codigo - precos de
nuvem mudam, e o valor deste projeto esta na metodologia de calculo,
nao numa cotacao permanentemente valida. Detalhes completos em
[docs/01-metodologia.md](docs/01-metodologia.md).
