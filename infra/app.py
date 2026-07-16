#!/usr/bin/env python3
"""CDK app do Exam Correction v2 (1 stack).

Região fixada em us-east-1 por padrão (necessário para WAF de escopo CLOUDFRONT e melhor
cobertura de modelos/AgentCore). Parâmetros vêm de contexto (-c) preenchido pelo deploy.sh.
"""
import os

import aws_cdk as cdk

from exam_stack import ExamStack

app = cdk.App()

region = os.environ.get("AWS_REGION") or os.environ.get("CDK_DEFAULT_REGION") or "us-east-1"
account = os.environ.get("CDK_DEFAULT_ACCOUNT")
stack_name = app.node.try_get_context("stackName") or os.environ.get("STACK_NAME", "exam-correction-v2")

ExamStack(
    app, stack_name,
    env=cdk.Environment(account=account, region=region),
    description="Exam Correction v2 — correção de provas com agentes no AgentCore Runtime.",
)

app.synth()
