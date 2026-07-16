import os
import random

from common import json_utils, metrics, model_config, ids
from common.rubric_seed import ENEM_RUBRIC


def test_extract_json_com_cercas_e_embutido():
    assert json_utils.extract_json('```json\n{"a":1}\n```') == {"a": 1}
    assert json_utils.extract_json('{"a":2}') == {"a": 2}
    assert json_utils.extract_json('lixo antes {"a":3} lixo depois') == {"a": 3}


def test_estimate_cost(monkeypatch):
    monkeypatch.setenv("MODEL_PRICING", '{"m1":{"in":0.003,"out":0.015}}')
    assert metrics.estimate_cost("m1", 1000, 1000) == round(0.003 + 0.015, 6)
    assert metrics.estimate_cost("desconhecido", 1000, 1000) is None


def test_should_run_challenger():
    assert model_config.should_run_challenger({"challengerModel": "", "abPolicy": {"percent": 100}}) is False
    assert model_config.should_run_challenger({"challengerModel": "c", "abPolicy": {"percent": 0}}) is False
    assert model_config.should_run_challenger({"challengerModel": "c", "abPolicy": {"percent": 100}}) is True
    # determinístico com rng semeado
    cfg = {"challengerModel": "c", "abPolicy": {"percent": 50}}
    r1 = model_config.should_run_challenger(cfg, random.Random(1))
    assert isinstance(r1, bool)


def test_test_id():
    tid = ids.generate_test_id()
    assert len(tid) == 10
    assert all(c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for c in tid)
    assert ids.generate_test_id() != ids.generate_test_id()


def test_rubrica_enem():
    assert ENEM_RUBRIC["totalMaxScore"] == 1000
    assert len(ENEM_RUBRIC["criteria"]) == 5
    assert sum(c["maxScore"] for c in ENEM_RUBRIC["criteria"]) == 1000
