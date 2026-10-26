"""
handler.py - CloudFormation Custom Resource that creates/updates/deletes the
INFERENCE TARGET (bedrock-mantle connector) on the Gateway.

Why a Custom Resource (Lambda) instead of a native CDK resource?
The CloudFormation resource type "AWS::BedrockAgentCore::GatewayTarget" still
only models targetConfiguration.{Http, Mcp} - the "inference" type (used by
inference targets, including the zero-config bedrock-mantle connector) is not
yet supported in the CloudFormation schema, even though the service API already
accepts it. This Custom Resource calls the real API via boto3 (which already
supports 'inference') until CloudFormation reaches parity.

Custom Resource protocol (CDK Provider Framework): receives an event with a
RequestType of Create/Update/Delete and returns a PhysicalResourceId + Data.
"""

import boto3
from botocore.exceptions import ClientError

REGION_ENV_KEY = "AWS_REGION"


def _client():
    import os
    return boto3.client("bedrock-agentcore-control", region_name=os.environ[REGION_ENV_KEY])


def on_event(event, context):  # noqa: ARG001
    request_type = event["RequestType"]
    props = event["ResourceProperties"]
    if request_type == "Create":
        return _create(props)
    if request_type == "Update":
        return _update(event, props)
    if request_type == "Delete":
        return _delete(event, props)
    raise ValueError(f"Unknown RequestType: {request_type}")


def _target_config(connector_id: str) -> dict:
    return {"inference": {"connector": {"source": {"connectorId": connector_id}}}}


def _create(props):
    cp = _client()
    resp = cp.create_gateway_target(
        gatewayIdentifier=props["GatewayIdentifier"],
        name=props["TargetName"],
        targetConfiguration=_target_config(props["ConnectorId"]),
        credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
    )
    target_id = resp["targetId"]
    return {
        "PhysicalResourceId": target_id,
        "Data": {"TargetId": target_id},
    }


def _update(event, props):
    # The name/connector do not change in this demo; if they do, recreating
    # (delete + create) is simpler and safer than attempting a partial update.
    _delete(event, props)
    return _create(props)


def _delete(event, props):
    cp = _client()
    target_id = event.get("PhysicalResourceId")
    if not target_id:
        return {"PhysicalResourceId": target_id or "none"}
    try:
        cp.delete_gateway_target(
            gatewayIdentifier=props["GatewayIdentifier"],
            targetId=target_id,
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("ResourceNotFoundException",):
            raise
    return {"PhysicalResourceId": target_id}
