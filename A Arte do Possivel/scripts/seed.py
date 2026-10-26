#!/usr/bin/env python3
"""Semeia a rubrica ENEM padrão e, se DEFAULT_MODEL_ID estiver definido, a model_config.

Idempotente: sobrescreve as sementes conhecidas (não duplica). Lê os nomes das tabelas dos
outputs da stack (via describe-stacks) para não depender de nomes fixos.
"""
import os
import sys

import time
from decimal import Decimal

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "avaliacao", "backend"))
from common.rubric_seed import ENEM_RUBRIC  # noqa: E402
from common.model_config import CAPABILITIES  # noqa: E402
from common.metrics import price_for  # noqa: E402

STACK_NAME = os.environ.get("STACK_NAME", "exam-correction-v2")
REGION = os.environ.get("AWS_REGION", "us-east-1")
# Modelo padrão do projeto: Sonnet 4.6 (usado em todas as capacidades por padrão).
DEFAULT_MODEL_ID = os.environ.get("DEFAULT_MODEL_ID", "").strip() or "us.anthropic.claude-sonnet-4-6"

cfn = boto3.client("cloudformation", region_name=REGION)
ddb = boto3.resource("dynamodb", region_name=REGION)


def _physical_id(logical_prefix: str) -> str:
    """Descobre o nome real da tabela pelo recurso lógico (prefixo)."""
    resources = cfn.list_stack_resources(StackName=STACK_NAME)["StackResourceSummaries"]
    for r in resources:
        if r["ResourceType"] == "AWS::DynamoDB::Table" and r["LogicalResourceId"].startswith(logical_prefix):
            return r["PhysicalResourceId"]
    raise SystemExit(f"Tabela {logical_prefix} não encontrada na stack {STACK_NAME}.")


def seed_pricing(mc) -> None:
    """Popula os preços por modelo (item __pricing__) com os VALORES DE LISTA (referência por
    família em common.metrics), para os modelos configurados. Preserva preços já definidos
    (manuais/anteriores); só preenche os que faltam. Idempotente."""
    models = set()
    if DEFAULT_MODEL_ID:
        models.add(DEFAULT_MODEL_ID)
    for cap in CAPABILITIES:
        item = mc.get_item(Key={"capability": cap}).get("Item") or {}
        for k in ("primaryModel", "challengerModel"):
            v = (item.get(k) or "").strip()
            if v:
                models.add(v)
    if not models:
        print(">> Sem modelos configurados — preços não semeados.")
        return
    existing = (mc.get_item(Key={"capability": "__pricing__"}).get("Item") or {}).get("prices") or {}
    prices = dict(existing)
    added = 0
    for m in sorted(models):
        if m in prices:
            continue  # preserva preço já definido (manual/anterior)
        p = price_for(m)
        if p:
            prices[m] = {"in": Decimal(str(p["in"])), "out": Decimal(str(p["out"]))}
            added += 1
    mc.put_item(Item={"capability": "__pricing__", "prices": prices,
                      "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    print(f">> Preços por modelo semeados (valores de lista): +{added}, total {len(prices)}.")


def main():
    rubrics = ddb.Table(_physical_id("Rubrics"))
    rubrics.put_item(Item=ENEM_RUBRIC)
    print(f">> Rubrica ENEM semeada ({ENEM_RUBRIC['rubricId']} v{ENEM_RUBRIC['version']}).")

    # Default = Sonnet 4.6 para toda capacidade SEM modelo (preserva escolhas já feitas).
    mc = ddb.Table(_physical_id("ModelConfig"))
    seeded = []
    for cap in CAPABILITIES:
        existing = mc.get_item(Key={"capability": cap}).get("Item") or {}
        if (existing.get("primaryModel") or "").strip():
            continue  # já configurado (UI/anterior) — não sobrescreve
        mc.put_item(Item={"capability": cap, "primaryModel": DEFAULT_MODEL_ID,
                          "challengerModel": "", "mode": "single", "abPolicy": {"percent": 0}})
        seeded.append(cap)
    print(f">> model_config: default {DEFAULT_MODEL_ID} aplicado a {len(seeded)} capacidade(s) sem modelo.")

    # Preços por modelo (valores de lista) — preenche os que faltam, preserva manuais.
    seed_pricing(mc)


if __name__ == "__main__":
    main()
