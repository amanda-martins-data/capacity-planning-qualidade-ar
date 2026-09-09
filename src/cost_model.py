"""
cost_model.py
--------------
Modelo de capacidade e custo para a infraestrutura real do Projeto 04
(Lambda + S3 + RDS Postgres), parametrizado por volume de leituras
diarias. Calcula duracao estimada de execucao da Lambda, custo mensal
projetado por servico, e o ponto de ruptura exato (em leituras/dia)
em que a Lambda excede o limite de 900 segundos (15 minutos).

Todos os precos sao valores de referencia aproximados (regiao us-east-1,
sem desconto de volume ou Savings Plan), documentados com a data de
referencia em PRICING_REFERENCE_DATE - precos de nuvem mudam, e este
modelo existe para mostrar a metodologia de calculo, nao para ser uma
cotacao valida indefinidamente.
"""

from __future__ import annotations

from dataclasses import dataclass

PRICING_REFERENCE_DATE = "2026-09"

# --- Volume base (linha de base real do Projeto 04) ---
BASELINE_CITIES = 3
BASELINE_POLLUTANTS = 5
BASELINE_READINGS_PER_DAY_PER_CITY_POLLUTANT = 24  # leitura horaria

# --- Parametros de tempo de execucao da Lambda ---
LAMBDA_FIXED_OVERHEAD_SECONDS = 5.0  # cold start + setup de conexao
LAMBDA_TIME_PER_READING_SECONDS = 0.05  # extracao/validacao/transformacao
LAMBDA_TIME_PER_UPSERT_ROW_SECONDS = 0.005  # upsert individual no RDS (nao em lote)
LAMBDA_TIMEOUT_LIMIT_SECONDS = 900.0  # limite duro da AWS Lambda (15 min)

# --- Precos de referencia AWS, us-east-1, sem desconto (PRICING_REFERENCE_DATE) ---
LAMBDA_PRICE_PER_GB_SECOND = 0.0000166667
LAMBDA_PRICE_PER_REQUEST = 0.0000002
LAMBDA_MEMORY_MB_DEFAULT = 256

S3_PRICE_PER_GB_MONTH = 0.023  # S3 Standard
S3_PRICE_PER_1000_PUT = 0.005
AVG_OBJECT_SIZE_KB = 0.5  # tamanho medio de um objeto JSON de leitura na Bronze

RDS_INSTANCE_PRICE_PER_HOUR = {
    "db.t3.micro": 0.017,
    "db.t3.small": 0.034,
    "db.t3.medium": 0.068,
}
RDS_STORAGE_PRICE_PER_GB_MONTH = 0.115  # gp2


def readings_per_day(scale_multiplier: float) -> int:
    """Numero de leituras brutas por dia, dado um multiplicador sobre
    a linha de base real do Projeto 04 (3 cidades x 5 poluentes x
    24 leituras/dia = 360 leituras/dia)."""
    baseline = BASELINE_CITIES * BASELINE_POLLUTANTS * BASELINE_READINGS_PER_DAY_PER_CITY_POLLUTANT
    return round(baseline * scale_multiplier)


def lambda_duration_seconds(readings: int) -> float:
    """Duracao estimada de uma unica invocacao da Lambda que processa
    `readings` leituras: overhead fixo + tempo de transformacao +
    tempo de upsert linha a linha no RDS (a arquitetura atual do
    Projeto 04 nao usa upsert em lote)."""
    return (
        LAMBDA_FIXED_OVERHEAD_SECONDS
        + readings * LAMBDA_TIME_PER_READING_SECONDS
        + readings * LAMBDA_TIME_PER_UPSERT_ROW_SECONDS
    )


def find_lambda_timeout_breakpoint() -> int:
    """Calcula o numero exato de leituras/dia em que a duracao
    estimada da Lambda ultrapassa o limite de 900 segundos.
    Resolve algebricamente em vez de forca bruta: 900 = overhead +
    readings * (tempo_por_leitura + tempo_por_upsert)."""
    tempo_por_leitura_total = LAMBDA_TIME_PER_READING_SECONDS + LAMBDA_TIME_PER_UPSERT_ROW_SECONDS
    readings_no_limite = (LAMBDA_TIMEOUT_LIMIT_SECONDS - LAMBDA_FIXED_OVERHEAD_SECONDS) / tempo_por_leitura_total
    return int(readings_no_limite)


def lambda_cost_monthly(readings: int, memory_mb: int = LAMBDA_MEMORY_MB_DEFAULT, invocations_per_day: int = 1) -> float:
    """Custo mensal estimado da Lambda: custo por requisicao +
    custo por GB-segundo consumido, assumindo `invocations_per_day`
    execucoes por dia (o Projeto 04 roda uma vez ao dia)."""
    duration = lambda_duration_seconds(readings)
    gb_seconds_per_invocation = (memory_mb / 1024) * duration
    invocations_per_month = invocations_per_day * 30

    request_cost = invocations_per_month * LAMBDA_PRICE_PER_REQUEST
    compute_cost = invocations_per_month * gb_seconds_per_invocation * LAMBDA_PRICE_PER_GB_SECOND

    return round(request_cost + compute_cost, 4)


def s3_cost_monthly(readings: int) -> float:
    """Custo mensal estimado de armazenamento e escrita em S3 para as
    camadas Bronze e Silver, assumindo retencao continua (o volume do
    mes acumula, mas para esta estimativa consideramos apenas o
    volume gravado no mes corrente, nao o historico acumulado de
    anos anteriores)."""
    readings_per_month = readings * 30
    storage_gb = (readings_per_month * AVG_OBJECT_SIZE_KB) / (1024 * 1024)
    storage_cost = storage_gb * S3_PRICE_PER_GB_MONTH
    put_cost = (readings_per_month / 1000) * S3_PRICE_PER_1000_PUT

    return round(storage_cost + put_cost, 4)


def rds_cost_monthly(instance_class: str = "db.t3.micro", storage_gb: float = 20.0) -> float:
    """Custo mensal estimado do RDS Postgres: instancia (fixo, nao
    depende do volume de leituras neste modelo, ja que a instancia
    fica ligada o mes inteiro independente do volume processado) +
    armazenamento."""
    hours_per_month = 24 * 30
    instance_cost = RDS_INSTANCE_PRICE_PER_HOUR[instance_class] * hours_per_month
    storage_cost = storage_gb * RDS_STORAGE_PRICE_PER_GB_MONTH

    return round(instance_cost + storage_cost, 2)


@dataclass
class ScenarioCost:
    scale_multiplier: float
    readings_per_day: int
    lambda_duration_seconds: float
    exceeds_lambda_timeout: bool
    lambda_cost_monthly: float
    s3_cost_monthly: float
    rds_cost_monthly: float

    @property
    def total_cost_monthly(self) -> float:
        return round(self.lambda_cost_monthly + self.s3_cost_monthly + self.rds_cost_monthly, 2)


def build_scenario(scale_multiplier: float) -> ScenarioCost:
    """Monta o cenario completo de custo e capacidade para um dado
    multiplicador de escala sobre a linha de base do Projeto 04."""
    readings = readings_per_day(scale_multiplier)
    duration = lambda_duration_seconds(readings)

    return ScenarioCost(
        scale_multiplier=scale_multiplier,
        readings_per_day=readings,
        lambda_duration_seconds=round(duration, 2),
        exceeds_lambda_timeout=duration > LAMBDA_TIMEOUT_LIMIT_SECONDS,
        lambda_cost_monthly=lambda_cost_monthly(readings),
        s3_cost_monthly=s3_cost_monthly(readings),
        rds_cost_monthly=rds_cost_monthly(),
    )
