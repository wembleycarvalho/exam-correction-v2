#!/usr/bin/env python3
"""CDK app entry point. A single stack with everything (Cognito, Gateway,
Lambda, S3, CloudFront)."""
import aws_cdk as cdk

from websearch_infra.stack import WebSearchDemoStack

app = cdk.App()
WebSearchDemoStack(app, "WebSearchDemoStack")
app.synth()
