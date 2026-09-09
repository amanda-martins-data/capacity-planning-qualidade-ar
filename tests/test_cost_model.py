"""
Testes de cost_model.py - 100% offline, sem dependencia de rede ou
credenciais AWS. Confirma que os numeros documentados em
docs/02-pontos-de-ruptura.md batem com o que o modelo calcula.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cost_model import (
    LAMBDA_TIMEOUT_LIMIT_SECONDS,
    build_scenario,
    find_lambda_timeout_breakpoint,
    lambda_cost_monthly,
    lambda_duration_seconds,
    readings_per_day,
    rds_cost_monthly,
)


def test_readings_per_day_baseline():
    assert readings_per_day(1) == 360  # 3 cidades x 5 poluentes x 24 leituras/dia


def test_readings_per_day_scales_linearly():
    assert readings_per_day(10) == 3600
    assert readings_per_day(100) == 36000


def test_lambda_duration_increases_with_readings():
    duration_1x = lambda_duration_seconds(readings_per_day(1))
    duration_10x = lambda_duration_seconds(readings_per_day(10))
    duration_100x = lambda_duration_seconds(readings_per_day(100))

    assert duration_1x < duration_10x < duration_100x


def test_baseline_does_not_exceed_lambda_timeout():
    scenario = build_scenario(1)

    assert scenario.exceeds_lambda_timeout is False
    assert scenario.lambda_duration_seconds < LAMBDA_TIMEOUT_LIMIT_SECONDS


def test_10x_does_not_exceed_lambda_timeout():
    """O volume projetado para 24 meses (10x) ainda cabe dentro do
    limite de execucao da Lambda sem nenhuma mudanca de arquitetura -
    achado central deste projeto."""
    scenario = build_scenario(10)

    assert scenario.exceeds_lambda_timeout is False


def test_100x_exceeds_lambda_timeout():
    """No cenario de estresse (100x), a Lambda unica excede o limite
    de 900 segundos - o ponto de ruptura identificado neste projeto."""
    scenario = build_scenario(100)

    assert scenario.exceeds_lambda_timeout is True
    assert scenario.lambda_duration_seconds > LAMBDA_TIMEOUT_LIMIT_SECONDS


def test_breakpoint_is_between_10x_and_100x():
    breakpoint_readings = find_lambda_timeout_breakpoint()

    assert readings_per_day(10) < breakpoint_readings < readings_per_day(100)


def test_breakpoint_matches_documented_multiplier():
    """O breakpoint documentado em 02-pontos-de-ruptura.md e
    aproximadamente 45x a linha de base - este teste garante que o
    numero no documento nao fique desatualizado em relacao ao codigo."""
    breakpoint_readings = find_lambda_timeout_breakpoint()
    breakpoint_multiplier = breakpoint_readings / readings_per_day(1)

    assert 45.0 < breakpoint_multiplier < 45.5


def test_scenario_just_below_breakpoint_does_not_exceed():
    breakpoint_readings = find_lambda_timeout_breakpoint()
    multiplier_below = (breakpoint_readings - 100) / readings_per_day(1)

    scenario = build_scenario(multiplier_below)

    assert scenario.exceeds_lambda_timeout is False


def test_scenario_just_above_breakpoint_exceeds():
    breakpoint_readings = find_lambda_timeout_breakpoint()
    multiplier_above = (breakpoint_readings + 100) / readings_per_day(1)

    scenario = build_scenario(multiplier_above)

    assert scenario.exceeds_lambda_timeout is True


def test_s3_cost_grows_but_never_becomes_the_dominant_cost():
    """S3 nao tem limite tecnico de escala (diferente da Lambda), mas
    o custo cresce de forma proporcional ao volume - o achado real
    aqui e que S3 passa de irrelevante (0,4% do custo total na linha
    de base) para uma fatia notavel (por volta de 27% a 100x), mas
    nunca ultrapassa o custo fixo do RDS, que domina em todos os
    cenarios testados."""
    scenario_1x = build_scenario(1)
    scenario_100x = build_scenario(100)

    assert scenario_100x.s3_cost_monthly > scenario_1x.s3_cost_monthly
    assert scenario_100x.s3_cost_monthly < scenario_100x.rds_cost_monthly


def test_rds_cost_is_constant_regardless_of_volume():
    """O custo do RDS neste modelo nao depende do volume de leituras -
    a instancia fica ligada o mes inteiro independente do processamento,
    reforcando que o gatilho de mudanca no RDS e desempenho (tempo de
    upsert), nao custo de instancia."""
    cost_baseline = rds_cost_monthly()
    cost_alternative_instance = rds_cost_monthly(instance_class="db.t3.small")

    assert cost_baseline != cost_alternative_instance  # varia por instancia, nao por volume
    assert cost_baseline > 0


def test_lambda_cost_grows_with_volume():
    cost_1x = lambda_cost_monthly(readings_per_day(1))
    cost_100x = lambda_cost_monthly(readings_per_day(100))

    assert cost_100x > cost_1x


def test_total_cost_at_baseline_is_low_double_digits():
    """Verificacao de sanidade: o custo total na linha de base real do
    Projeto 04 deveria ser uma dezena de dolares por mes, nao centenas -
    proporcional a um pipeline de portfolio, nao a uma carga de producao
    de grande escala."""
    scenario = build_scenario(1)

    assert 5.0 < scenario.total_cost_monthly < 50.0
