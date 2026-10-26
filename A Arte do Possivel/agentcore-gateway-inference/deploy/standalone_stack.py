"""Stack STANDALONE do módulo AgentCore — Gateway Inference (deploy cirúrgico, reproduzível).

Cria só o backend do módulo (Router Lambda + HTTP API + authorizer Cognito importado do
portal + IAM least-privilege), sem tocar no stack do portal. A rota /agentcore/* é ligada à
distribution existente por `cloudfront_behavior.py`.

O Router faz a ponte para o AgentCore Runtime (agente `gateway_inference`) e lista modelos do
Gateway existente. Config vem do SSM `/gateway-inference/*`; o segredo m2m fica no Secrets
Manager (nunca no código/bundle). Env: OCTX_USER_POOL_ID, OCTX_CLIENT_ID.
"""
import os
from aws_cdk import (
    Stack, Duration, CfnOutput,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as apigw_authz,
    aws_cognito as cognito,
)
from constructs import Construct


class GwInfStandaloneStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        region, account = self.region, self.account
        secret_arn = os.environ["GWINF_SECRET_ARN"]  # ARN do segredo m2m (do InferenceDemoStack)

        pool = cognito.UserPool.from_user_pool_id(self, "Pool", os.environ["OCTX_USER_POOL_ID"])
        client = cognito.UserPoolClient.from_user_pool_client_id(
            self, "Client", os.environ["OCTX_CLIENT_ID"])

        layer = lambda_.LayerVersion(
            self, "Boto3", code=lambda_.Code.from_asset("layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="boto3 recente (bedrock-agentcore InvokeAgentRuntime)")

        fn = lambda_.Function(
            self, "RouterFn", runtime=lambda_.Runtime.PYTHON_3_12, handler="handler.handler",
            code=lambda_.Code.from_asset("../api", exclude=["**/__pycache__", "*.pyc"]),
            timeout=Duration.seconds(60), memory_size=512, layers=[layer])

        # Ponte para o AgentCore Runtime do módulo.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=[f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/gateway_inference-*"]))
        # Config no SSM + segredo m2m (listar modelos / mintar token).
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter", "ssm:GetParameters"],
            resources=[f"arn:aws:ssm:{region}:{account}:parameter/gateway-inference/*"]))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"], resources=[secret_arn]))
        # Observability do Gateway (Mantle-config): metricas AWS/BedrockMantle no CloudWatch.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["cloudwatch:ListMetrics", "cloudwatch:GetMetricData"], resources=["*"]))

        authorizer = apigw_authz.HttpUserPoolAuthorizer("Jwt", pool, user_pool_clients=[client])
        http_api = apigw.HttpApi(self, "Api", create_default_stage=True)
        integ = integrations.HttpLambdaIntegration("Integ", fn)
        http_api.add_routes(path="/agentcore/health",
                            methods=[apigw.HttpMethod.GET], integration=integ)
        http_api.add_routes(path="/agentcore/{proxy+}", methods=[apigw.HttpMethod.ANY],
                            integration=integ, authorizer=authorizer)

        CfnOutput(self, "ApiDomain",
                  value=f"{http_api.http_api_id}.execute-api.{region}.amazonaws.com")
        CfnOutput(self, "RouterFnName", value=fn.function_name)
