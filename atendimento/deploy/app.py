#!/usr/bin/env python3
import os
import aws_cdk as cdk
from standalone_stack import AtendimentoStandaloneStack

app = cdk.App()
AtendimentoStandaloneStack(
    app, "atendimento",
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")),
    description="Atendimento (standalone) - backend serverless do modulo do portal (templates + campanhas).",
)
app.synth()
