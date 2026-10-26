#!/usr/bin/env python3
"""CDK app entry point. A single stack with everything (Cognito, Gateway,
Fargate/ALB, S3, CloudFront)."""
import os

import aws_cdk as cdk

from inference_infra.stack import InferenceDemoStack

app = cdk.App()

# An explicit account/region is required so the stack can look up an existing
# VPC (ec2.Vpc.from_lookup, used when you pass -c vpcId=...). The CDK CLI sets
# CDK_DEFAULT_ACCOUNT/REGION from your current credentials/profile.
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)
InferenceDemoStack(app, "InferenceDemoStack", env=env)
app.synth()
