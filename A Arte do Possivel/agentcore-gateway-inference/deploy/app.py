#!/usr/bin/env python3
import os
import aws_cdk as cdk
from standalone_stack import GwInfStandaloneStack

app = cdk.App()
GwInfStandaloneStack(
    app, "agentcore-gateway-inference",
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")),
    description="AgentCore Gateway Inference (standalone) - backend serverless do modulo do portal.",
)
app.synth()
