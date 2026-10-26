#!/usr/bin/env python3
import os
import aws_cdk as cdk
from standalone_stack import OctxStandaloneStack

app = cdk.App()
OctxStandaloneStack(
    app, "orientador-context",
    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")),
    description="Orientador Context (standalone) - backend serverless do modulo do portal.",
)
app.synth()
