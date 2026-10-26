"""
handler.py - CloudFormation Custom Resource that restricts the backend ALB's
security group so it only accepts traffic from the CloudFront VPC Origin.

Why a Custom Resource? The internal ALB is reached exclusively through a
CloudFront VPC Origin. CloudFront creates a managed, account/VPC-level security
group named "CloudFront-VPCOrigins-Service-SG" (tagged aws.cloudfront.vpcorigin)
only AFTER the VPC origin is provisioned - so its id is not known at synth time
and cannot be referenced directly in the CDK app. This resource looks it up at
deploy time and authorizes ingress on the ALB's security group from it. Combined
with `open_listener=False` on the Fargate service (which removes the default
0.0.0.0/0 rule), the ALB ends up reachable ONLY via CloudFront.
"""

import os
import time

import boto3
from botocore.exceptions import ClientError

CF_SG_NAME = "CloudFront-VPCOrigins-Service-SG"


def _ec2():
    return boto3.client("ec2", region_name=os.environ["AWS_REGION"])


def on_event(event, context):  # noqa: ARG001
    request_type = event["RequestType"]
    props = event["ResourceProperties"]
    if request_type == "Delete":
        # The ALB security group is deleted with the stack, so its rules go with
        # it - nothing to undo here.
        return {"PhysicalResourceId": event.get("PhysicalResourceId", "alb-sg-lock")}
    return _authorize(props)


def _authorize(props):
    ec2 = _ec2()
    alb_sg = props["AlbSecurityGroupId"]
    vpc_id = props["VpcId"]

    # The managed CloudFront VPC origins SG may appear a few seconds after the
    # VPC origin is provisioned - retry briefly.
    cf_sg = None
    for _ in range(10):
        resp = ec2.describe_security_groups(Filters=[
            {"Name": "group-name", "Values": [CF_SG_NAME]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ])
        groups = resp.get("SecurityGroups", [])
        if groups:
            cf_sg = groups[0]["GroupId"]
            break
        time.sleep(6)
    if not cf_sg:
        raise RuntimeError(
            f"CloudFront VPC origins SG '{CF_SG_NAME}' not found in {vpc_id}"
        )

    try:
        ec2.authorize_security_group_ingress(
            GroupId=alb_sg,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "UserIdGroupPairs": [{
                    "GroupId": cf_sg,
                    "Description": "CloudFront VPC Origin only",
                }],
            }],
        )
    except ClientError as exc:
        # Already authorized (e.g. on a stack update) - treat as success.
        if exc.response.get("Error", {}).get("Code") != "InvalidPermission.Duplicate":
            raise

    return {"PhysicalResourceId": "alb-sg-lock", "Data": {"CloudFrontSg": cf_sg}}
