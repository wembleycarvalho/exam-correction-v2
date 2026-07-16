#!/usr/bin/env python3
"""Semeia a rubrica ENEM padrão e, se DEFAULT_MODEL_ID estiver definido, a model_config.

Idempotente: sobrescreve as sementes conhecidas (não duplica). Lê os nomes das tabelas dos
outputs da stack (via describe-stacks) para não depender de nomes fixos.
"""
import os
import sys

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from common.rubric_seed import ENEM_RUBRIC  # noqa: E402
from common.model_config import CAPABILITIES  # noqa: E402

STACK_NAME = os.environ.get("STACK_NAME", "exam-correction-v2")
REGION = os.environ.get("AWS_REGION", "us-east-1")
DEFAULT_MODEL_ID = os.environ.get("DEFAULT_MODEL_ID", "").strip()

cfn = boto3.client("cloudformation", region_name=REGION)
ddb = boto3.resource("dynamodb", region_name=REGION)


def _physical_id(logical_prefix: str) -> str:
    """Descobre o nome real da tabela pelo recurso lógico (prefixo)."""
    resources = cfn.list_stack_resources(StackName=STACK_NAME)["StackResourceSummaries"]
    for r in resources:
        if r["ResourceType"] == "AWS::DynamoDB::Table" and r["LogicalResourceId"].startswith(logical_prefix):
            return r["PhysicalResourceId"]
    raise SystemExit(f"Tabela {logical_prefix} não encontrada na stack {STACK_NAME}.")


def main():
    rubrics = ddb.Table(_physical_id("Rubrics"))
    rubrics.put_item(Item=ENEM_RUBRIC)
    print(f">> Rubrica ENEM semeada ({ENEM_RUBRIC['rubricId']} v{ENEM_RUBRIC['version']}).")

    if DEFAULT_MODEL_ID:
        mc = ddb.Table(_physical_id("ModelConfig"))
        for cap in CAPABILITIES:
            mc.put_item(Item={"capability": cap, "primaryModel": DEFAULT_MODEL_ID,
                              "challengerModel": "", "abPolicy": {"percent": 0}})
        print(f">> model_config semeada com DEFAULT_MODEL_ID={DEFAULT_MODEL_ID}.")
    else:
        print(">> DEFAULT_MODEL_ID vazio — configure os modelos pela UI (Configuração de Modelos).")


if __name__ == "__main__":
    main()
