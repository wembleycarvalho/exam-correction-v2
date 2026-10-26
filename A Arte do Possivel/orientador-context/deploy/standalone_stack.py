"""Stack STANDALONE do Orientador Context (deploy cirúrgico, reproduzível).

Cria só o backend do módulo (Lambda agente + HTTP API + authorizer Cognito importado do portal
+ IAM least-privilege), sem tocar no stack do portal. É o caminho INTERINO enquanto o portal
não é redeployado via CDK (que exige Docker p/ a imagem do Entrevistador). A rota
/orientador-context/* é ligada à distribution existente por `cloudfront_behavior.py`.

Config vem por env: OCTX_LAKE_BUCKET, OCTX_USER_POOL_ID, OCTX_CLIENT_ID (e opcionais
OCTX_GLUE_DB, OCTX_WORKGROUP, OCTX_MODEL_ID). O código do agente é o mesmo do módulo
(`../agent`); a lógica canônica de infra CDK-gerenciada vive em `infra/modules/orientador_context.py`.
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


class OctxStandaloneStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        region, account = self.region, self.account

        lake = os.environ["OCTX_LAKE_BUCKET"]
        glue_db = os.environ.get("OCTX_GLUE_DB", "moodle_datalake")
        workgroup = os.environ.get("OCTX_WORKGROUP", "moodle-datalake")
        model_id = os.environ.get("OCTX_MODEL_ID", "amazon.nova-pro-v1:0")

        pool = cognito.UserPool.from_user_pool_id(self, "Pool", os.environ["OCTX_USER_POOL_ID"])
        client = cognito.UserPoolClient.from_user_pool_client_id(
            self, "Client", os.environ["OCTX_CLIENT_ID"])

        layer = lambda_.LayerVersion(
            self, "Boto3", code=lambda_.Code.from_asset("layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="boto3 recente (Bedrock Converse tool-use)")

        fn = lambda_.Function(
            self, "AgentFn", runtime=lambda_.Runtime.PYTHON_3_12, handler="handler.handler",
            code=lambda_.Code.from_asset("../agent", exclude=["**/__pycache__", "*.pyc"]),
            timeout=Duration.seconds(60), memory_size=512, layers=[layer],
            environment={"GLUE_DB": glue_db, "WORKGROUP": workgroup, "MODEL_ID": model_id,
                         "RUNTIME_ARN_PARAM": "/orientador-context/runtime-arn"})

        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["athena:StartQueryExecution", "athena:GetQueryExecution",
                     "athena:GetQueryResults", "athena:StopQueryExecution"],
            resources=[f"arn:aws:athena:{region}:{account}:workgroup/{workgroup}"]))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["glue:GetDatabase", "glue:GetTable", "glue:GetTables",
                     "glue:GetPartition", "glue:GetPartitions"],
            resources=[f"arn:aws:glue:{region}:{account}:catalog",
                       f"arn:aws:glue:{region}:{account}:database/{glue_db}",
                       f"arn:aws:glue:{region}:{account}:table/{glue_db}/*"]))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:GetBucketLocation", "s3:ListBucket"],
            resources=[f"arn:aws:s3:::{lake}"]))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:PutObject"], resources=[f"arn:aws:s3:::{lake}/*"]))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=["arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                       "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                       f"arn:aws:bedrock:*:{account}:inference-profile/*"]))
        # Ponte p/ o AgentCore Runtime (chat agêntico) + leitura do ARN via SSM.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=[f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/orientador_context-*"]))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{region}:{account}:parameter/orientador-context/*"]))

        authorizer = apigw_authz.HttpUserPoolAuthorizer("Jwt", pool, user_pool_clients=[client])
        http_api = apigw.HttpApi(self, "Api", create_default_stage=True)
        integ = integrations.HttpLambdaIntegration("Integ", fn)
        http_api.add_routes(path="/orientador-context/health",
                            methods=[apigw.HttpMethod.GET], integration=integ)
        http_api.add_routes(path="/orientador-context/{proxy+}", methods=[apigw.HttpMethod.ANY],
                            integration=integ, authorizer=authorizer)

        CfnOutput(self, "ApiDomain",
                  value=f"{http_api.http_api_id}.execute-api.{region}.amazonaws.com")
        CfnOutput(self, "AgentFnName", value=fn.function_name)
