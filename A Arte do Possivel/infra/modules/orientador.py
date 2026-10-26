"""Módulo Orientador Acadêmico — 100% desacoplado do módulo de correção.

Knowledge graph em **Amazon Neptune Serverless** (VPC padrão) + agente **Strands** no
**AgentCore Runtime** (container ECR, anexado à VPC para alcançar o Neptune). O browser
nunca fala com o Runtime: um **bridge Lambda** (atrás de HTTP API + Cognito, servido pelo
mesmo CloudFront sob /orientador/*) resolve o ARN do agente (SSM) e faz InvokeAgentRuntime.

O AgentCore Runtime é criado FORA do CDK por scripts/deploy-orientador-agent.sh (starter
toolkit, imagem ECR, VPC), que publica o ARN no SSM param criado aqui — mesmo padrão do
módulo de correção.
"""
from aws_cdk import (
    Duration, CfnOutput, Stack,
    aws_ec2 as ec2,
    aws_neptune as neptune,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as apigw_authz,
)
from constructs import Construct


class OrientadorModule(Construct):
    """Expõe `self.api_domain` para o portal registrar o behavior /orientador/* no CloudFront."""

    def __init__(self, scope: Construct, cid: str, *, stack_name: str, user_pool,
                 user_pool_client, boto3_layer, model_id: str = "amazon.nova-pro-v1:0",
                 **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)

        vpc = ec2.Vpc.from_lookup(self, "Vpc", is_default=True)
        subnet_ids = vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnet_ids

        # --- Security groups: agente -> Neptune (8182) ---
        agent_sg = ec2.SecurityGroup(self, "AgentSg", vpc=vpc, allow_all_outbound=True,
                                     description="AgentCore Runtime do Orientador")
        neptune_sg = ec2.SecurityGroup(self, "NeptuneSg", vpc=vpc, allow_all_outbound=True,
                                       description="Neptune do Orientador")
        neptune_sg.add_ingress_rule(agent_sg, ec2.Port.tcp(8182), "openCypher a partir do agente")

        # --- Neptune Serverless ---
        subnet_group = neptune.CfnDBSubnetGroup(
            self, "NeptuneSubnets",
            db_subnet_group_description="Orientador Neptune subnet group",
            subnet_ids=subnet_ids,
        )
        cluster = neptune.CfnDBCluster(
            self, "NeptuneCluster",
            db_subnet_group_name=subnet_group.ref,
            vpc_security_group_ids=[neptune_sg.security_group_id],
            iam_auth_enabled=True,
            serverless_scaling_configuration=neptune.CfnDBCluster.ServerlessScalingConfigurationProperty(
                min_capacity=1.0, max_capacity=4.0),
        )
        cluster.add_dependency(subnet_group)
        instance = neptune.CfnDBInstance(
            self, "NeptuneInstance",
            db_instance_class="db.serverless",
            db_cluster_identifier=cluster.ref,
        )
        instance.add_dependency(cluster)

        neptune_endpoint = cluster.attr_endpoint

        # --- Role de execução do agente (AgentCore Runtime) ---
        # Passada ao starter toolkit via --execution-role. Precisa: consultar o Neptune
        # (IAM auth) + invocar modelos Bedrock + logs.
        stack = Stack.of(self)
        runtime_role = iam.Role(
            self, "AgentRuntimeRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description="Execução do agente Orientador no AgentCore Runtime",
        )
        runtime_role.add_to_policy(iam.PolicyStatement(
            actions=["neptune-db:connect", "neptune-db:ReadDataViaQuery",
                     "neptune-db:WriteDataViaQuery", "neptune-db:DeleteDataViaQuery",
                     "neptune-db:GetQueryStatus"],
            resources=[f"arn:aws:neptune-db:{stack.region}:{stack.account}:"
                       f"{cluster.attr_cluster_resource_id}/*"],
        ))
        runtime_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                "arn:aws:bedrock:*:*:inference-profile/*",
            ],
        ))
        runtime_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"]))
        # Pull da imagem do agente no ECR (o Runtime em VPC baixa a imagem com esta role).
        # GetAuthorizationToken não suporta escopo por recurso -> "*"; o pull é restrito
        # ao repositório do agente.
        runtime_role.add_to_policy(iam.PolicyStatement(
            actions=["ecr:GetAuthorizationToken"], resources=["*"]))
        runtime_role.add_to_policy(iam.PolicyStatement(
            actions=["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer",
                     "ecr:BatchGetImage"],
            resources=[f"arn:aws:ecr:{stack.region}:{stack.account}:repository/orientador-agent"],
        ))

        # --- SSM: ARN do AgentCore Runtime (publicado pelo deploy do agente) ---
        runtime_arn_param = ssm.StringParameter(
            self, "OrientadorRuntimeArnParam",
            parameter_name=f"/{stack_name}/orientador-runtime-arn",
            string_value="PENDING",
            description="ARN do AgentCore Runtime do Orientador (deploy-orientador-agent.sh).",
        )

        # --- Bridge Lambda: HTTP -> InvokeAgentRuntime ---
        bridge_fn = lambda_.Function(
            self, "BridgeFn", runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../orientador-academico/bridge"),
            timeout=Duration.seconds(60), memory_size=256, layers=[boto3_layer],
            environment={"AGENT_RUNTIME_PARAM": runtime_arn_param.parameter_name},
        )
        runtime_arn_param.grant_read(bridge_fn)
        bridge_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"], resources=["*"]))

        # --- HTTP API + Cognito (mesma auth do portal) ---
        authorizer = apigw_authz.HttpUserPoolAuthorizer(
            "OrientadorJwt", user_pool, user_pool_clients=[user_pool_client])
        http_api = apigw.HttpApi(self, "OrientadorApi", create_default_stage=True)
        http_api.add_routes(
            path="/orientador/{proxy+}", methods=[apigw.HttpMethod.ANY],
            integration=integrations.HttpLambdaIntegration("OrientadorInteg", bridge_fn),
            authorizer=authorizer,
        )
        self.api_domain = f"{http_api.http_api_id}.execute-api.{stack.region}.amazonaws.com"

        # --- Outputs para o script de deploy do agente ---
        # OutputKeys estáveis (override_logical_id) para o script de deploy do agente ler.
        def _out(cid: str, key: str, value: str):
            o = CfnOutput(self, cid, value=value)
            o.override_logical_id(key)

        _out("OutNeptuneEndpoint", "OrientadorNeptuneEndpoint", neptune_endpoint)
        _out("OutAgentSg", "OrientadorAgentSg", agent_sg.security_group_id)
        _out("OutSubnets", "OrientadorSubnets", ",".join(subnet_ids))
        _out("OutRuntimeRoleArn", "OrientadorRuntimeRoleArn", runtime_role.role_arn)
        _out("OutRuntimeArnParam", "OrientadorRuntimeArnParam", runtime_arn_param.parameter_name)
        _out("OutModelId", "OrientadorModelId", model_id)
