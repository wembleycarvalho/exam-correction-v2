"""Resolução de modelo por capacidade (primário/challenger/A-B).

Os modelos NUNCA são hardcoded: vêm da tabela `model_config` (uma linha por capacidade),
configurável pela UI. Capacidades: `transcription`, `essay`, `exam`, `author`, `answersheet`.
"""
import os
import random

import boto3

MODEL_CONFIG_TABLE = os.environ.get("MODEL_CONFIG_TABLE", "")

CAPABILITIES = ("transcription", "essay", "exam", "author", "answersheet")


MODES = ("single", "ab", "both")  # só primário / A-B por % / rodar ambos e comparar


def get_card_template(template_id: str) -> dict:
    """Lê um template de cartão-resposta (guardado como item 'tmpl#<id>' em model_config)."""
    if not template_id:
        return None
    table = boto3.resource("dynamodb").Table(MODEL_CONFIG_TABLE)
    return table.get_item(Key={"capability": "tmpl#" + template_id}).get("Item")


def get_model_config(capability: str) -> dict:
    """Lê a config de modelo (primário/challenger/modo/abPolicy) para uma capacidade."""
    table = boto3.resource("dynamodb").Table(MODEL_CONFIG_TABLE)
    item = table.get_item(Key={"capability": capability}).get("Item") or {}
    ab = item.get("abPolicy") or {"percent": 0}
    mode = item.get("mode") or "single"
    return {
        "capability": capability,
        "primaryModel": item.get("primaryModel", "") or "",
        "challengerModel": item.get("challengerModel", "") or "",
        "mode": mode if mode in MODES else "single",
        "abPolicy": {"percent": int(ab.get("percent", 0) or 0)},
    }


def plan_runs(config: dict, rng: random.Random = None) -> list:
    """Decide quais execuções de correção rodar, conforme o modo.

    Retorna lista de {"model", "isChallenger"}:
      - single: só o primário (oficial);
      - ab: primário OU challenger, sorteado por abPolicy.percent (o escolhido é oficial);
      - both: primário (oficial) + challenger (comparação).
    """
    primary = config.get("primaryModel")
    challenger = config.get("challengerModel")
    mode = config.get("mode", "single")
    if not primary:
        return []
    if not challenger or mode == "single":
        return [{"model": primary, "isChallenger": False}]
    if mode == "both":
        return [{"model": primary, "isChallenger": False},
                {"model": challenger, "isChallenger": True}]
    # mode == "ab": uma OU outra, por percentual (percent = % que vai pro challenger)
    percent = int(config.get("abPolicy", {}).get("percent", 0) or 0)
    r = (rng or random).random() * 100.0
    chosen = challenger if r < percent else primary
    return [{"model": chosen, "isChallenger": False}]


def should_run_challenger(config: dict, rng: random.Random = None) -> bool:
    """Decide, pela abPolicy, se o challenger roda em shadow nesta submissão."""
    challenger = config.get("challengerModel")
    if not challenger:
        return False
    percent = int(config.get("abPolicy", {}).get("percent", 0) or 0)
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    r = rng or random
    return r.random() * 100.0 < percent
