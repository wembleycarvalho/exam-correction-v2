"""Módulo Orientador Context — novo, isolado e 100% aditivo.

Serverless SEM VPC (Athena/Glue/S3/Bedrock têm endpoints públicos), no molde do LMS. Um
agente em Lambda consome o data lake do Moodle (Glue catalog `moodle_datalake`) via Bedrock
Converse + tool-use, servido pelo mesmo CloudFront sob /orientador-context/* e protegido pelo
mesmo Cognito. Coexiste com o Orientador atual (Neptune) — nada do existente é tocado.

Consome os OUTPUTS do backbone Moodle (projeto apartado): o nome do bucket do data lake é
passado por contexto (`orientadorContextLakeBucket`); o Glue database e o workgroup do Athena
têm defaults estáveis (`moodle_datalake` / `moodle-datalake`).

Expõe `self.api_domain` para o portal registrar o behavior /orientador-context/*.
"""
from aws_cdk import (
    CfnOutput, Duration, Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_authorizers as apigw_authz,
    aws_apigatewayv2_integrations as integrations,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from constructs import Construct


class OrientadorContextModule(Construct):
    def __init__(self, scope: Construct, cid: str, *, stack_name: str, user_pool,
                 user_pool_client, boto3_layer, lake_bucket: str,
                 glue_db: str = "moodle_datalake", workgroup: str = "moodle-datalake",
                 model_id: str = "amazon.nova-pro-v1:0", **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        stack = Stack.of(self)
        region, account = stack.region, stack.account

        # --- Agente (Lambda): Converse + tool-use sobre o data lake via Athena ---
        agent_fn = lambda_.Function(
            self, "AgentFn", runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(
                "../orientador-context/agent",
                exclude=["**/__pycache__", "*.pyc", "tests"]),
            timeout=Duration.seconds(60), memory_size=512, layers=[boto3_layer],
            environment={"GLUE_DB": glue_db, "WORKGROUP": workgroup, "MODEL_ID": model_id},
        )

        # --- Permissões (privilégio mínimo) ---
        # Athena (só o workgroup do data lake)
        agent_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["athena:StartQueryExecution", "athena:GetQueryExecution",
                     "athena:GetQueryResults", "athena:StopQueryExecution"],
            resources=[f"arn:aws:athena:{region}:{account}:workgroup/{workgroup}"]))
        # Glue (catálogo/database/tabelas do data lake)
        agent_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["glue:GetDatabase", "glue:GetTable", "glue:GetTables",
                     "glue:GetPartition", "glue:GetPartitions"],
            resources=[
                f"arn:aws:glue:{region}:{account}:catalog",
                f"arn:aws:glue:{region}:{account}:database/{glue_db}",
                f"arn:aws:glue:{region}:{account}:table/{glue_db}/*"]))
        # S3 (lê os dados do lake; lê/escreve os resultados do Athena no mesmo bucket)
        if lake_bucket:
            agent_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[f"arn:aws:s3:::{lake_bucket}",
                           f"arn:aws:s3:::{lake_bucket}/*"]))
            agent_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[f"arn:aws:s3:::{lake_bucket}/athena-results/*"]))
        # Bedrock Converse (modelos Nova/Claude + perfis de inferência)
        agent_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                f"arn:aws:bedrock:*:{account}:inference-profile/*"]))

        # --- HTTP API + Cognito (mesma auth do portal) ---
        authorizer = apigw_authz.HttpUserPoolAuthorizer(
            "OrientadorContextJwt", user_pool, user_pool_clients=[user_pool_client])
        http_api = apigw.HttpApi(self, "OrientadorContextApi", create_default_stage=True)
        integ = integrations.HttpLambdaIntegration("OrientadorContextInteg", agent_fn)
        # Health público (sem JWT), como /lms/health e /entrevistador/health.
        http_api.add_routes(path="/orientador-context/health",
                            methods=[apigw.HttpMethod.GET], integration=integ)
        http_api.add_routes(
            path="/orientador-context/{proxy+}", methods=[apigw.HttpMethod.ANY],
            integration=integ, authorizer=authorizer)
        self.api_domain = f"{http_api.http_api_id}.execute-api.{region}.amazonaws.com"

        def _out(cid_: str, key: str, value: str):
            o = CfnOutput(self, cid_, value=value)
            o.override_logical_id(key)

        _out("OutApiId", "OrientadorContextApiId", http_api.http_api_id)
        _out("OutModelId", "OrientadorContextModelId", model_id)
        _out("OutGlueDb", "OrientadorContextGlueDb", glue_db)
