"""Stack STANDALONE do módulo Atendimento (deploy cirúrgico, reproduzível).

Cria só o backend do módulo (Router Lambda + HTTP API + authorizer Cognito importado do
portal + IAM least-privilege por serviço), sem tocar no stack do portal. A rota
/atendimento/* é ligada à distribution existente por `cloudfront_behavior.py`.

O Router porta o campaign_tester: templates WhatsApp (End User Messaging Social), envio 1-1,
e campanhas (Customer Profiles + Connect Outbound Campaigns + Q in Connect). Config vem do
SSM `/atendimento/*` (semeado pelo deploy.sh). Env do deploy: OCTX_USER_POOL_ID,
OCTX_CLIENT_ID, ATEND_CAMPAIGN_BUCKET, CONNECT_INSTANCE_ID.
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


class AtendimentoStandaloneStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        region, account = self.region, self.account
        bucket = os.environ.get("ATEND_CAMPAIGN_BUCKET", f"campanhas-connect-{account}")
        instance_id = os.environ.get("CONNECT_INSTANCE_ID", "82a1c25d-b923-4bd2-9c21-e7eba7f052ac")
        cp_domain = os.environ.get("CP_DOMAIN", "amazon-connect-connect-demo-ps")

        pool = cognito.UserPool.from_user_pool_id(self, "Pool", os.environ["OCTX_USER_POOL_ID"])
        client = cognito.UserPoolClient.from_user_pool_client_id(
            self, "Client", os.environ["OCTX_CLIENT_ID"])

        layer = lambda_.LayerVersion(
            self, "Boto3", code=lambda_.Code.from_asset("layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="boto3 recente (socialmessaging/connectcampaignsv2/qconnect)")

        fn = lambda_.Function(
            self, "RouterFn", runtime=lambda_.Runtime.PYTHON_3_12, handler="handler.handler",
            code=lambda_.Code.from_asset("../api", exclude=["**/__pycache__", "*.pyc"]),
            timeout=Duration.seconds(120), memory_size=512, layers=[layer])

        # --- IAM least-privilege por serviço ---
        # Config no SSM /atendimento/*
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter", "ssm:GetParameters"],
            resources=[f"arn:aws:ssm:{region}:{account}:parameter/atendimento/*"]))
        # WhatsApp (End User Messaging Social): listar/ler templates + enviar 1-1.
        # socialmessaging não tem ARNs de template granulares -> ações específicas em "*".
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["social-messaging:GetWhatsAppMessageTemplate",
                     "social-messaging:ListWhatsAppMessageTemplates",
                     "social-messaging:SendWhatsAppMessage"],
            resources=["*"]))
        # Customer Profiles: perfis, object types, segmentos, dedup, event trigger (no domínio).
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["profile:PutProfileObject", "profile:PutProfileObjectType",
                     "profile:GetProfileObjectType", "profile:SearchProfiles",
                     "profile:MergeProfiles", "profile:CreateSegmentDefinition",
                     "profile:DeleteSegmentDefinition", "profile:CreateEventTrigger",
                     "profile:GetSegmentDefinition"],
            resources=[f"arn:aws:profile:{region}:{account}:domains/{cp_domain}",
                       f"arn:aws:profile:{region}:{account}:domains/{cp_domain}/*"]))
        # S3: CSV da campanha no bucket dedicado.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
            resources=[f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]))
        # Q in Connect (Wisdom): message templates + tag.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["wisdom:ListMessageTemplates", "wisdom:CreateMessageTemplate",
                     "wisdom:GetMessageTemplate", "wisdom:RenderMessageTemplate",
                     "wisdom:TagResource"],
            resources=[f"arn:aws:wisdom:{region}:{account}:*"]))
        # Connect: flow de campanha (CAMPAIGN) na instância de demo.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["connect:CreateContactFlow", "connect:UpdateContactFlowContent",
                     "connect:CreateContactFlowVersion", "connect:ListContactFlows",
                     "connect:DescribeContactFlow"],
            resources=[f"arn:aws:connect:{region}:{account}:instance/{instance_id}",
                       f"arn:aws:connect:{region}:{account}:instance/{instance_id}/*"]))
        # Connect Outbound Campaigns v2: criar/iniciar/listar/tag campanha.
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["connect-campaigns:CreateCampaign", "connect-campaigns:StartCampaign",
                     "connect-campaigns:ListCampaigns", "connect-campaigns:TagResource",
                     "connect-campaigns:DescribeCampaign"],
            resources=["*"]))

        # --- Ponte de STREAMING (Node.js, response streaming) p/ o chat do assistente ---
        # Agente no AgentCore Runtime; esta Lambda repassa InvokeAgentRuntime como SSE ao
        # browser. Function URL em RESPONSE_STREAM; valida o JWT do portal no próprio código.
        bridge = lambda_.Function(
            self, "BridgeFn", runtime=lambda_.Runtime.NODEJS_22_X, handler="index.handler",
            code=lambda_.Code.from_asset("../bridge", exclude=["**/__pycache__"]),
            timeout=Duration.seconds(120), memory_size=512,
            environment={"POOL_ID": os.environ["OCTX_USER_POOL_ID"]})
        bridge.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{region}:{account}:parameter/atendimento/*"]))
        bridge.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"],
            resources=[f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/atendimento_assistant-*"]))
        bridge_url = bridge.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM)
        CfnOutput(self, "BridgeUrl", value=bridge_url.url)
        CfnOutput(self, "BridgeFnName", value=bridge.function_name)

        authorizer = apigw_authz.HttpUserPoolAuthorizer("Jwt", pool, user_pool_clients=[client])
        http_api = apigw.HttpApi(self, "Api", create_default_stage=True)
        integ = integrations.HttpLambdaIntegration("Integ", fn)
        http_api.add_routes(path="/atendimento/health",
                            methods=[apigw.HttpMethod.GET], integration=integ)
        http_api.add_routes(path="/atendimento/{proxy+}", methods=[apigw.HttpMethod.ANY],
                            integration=integ, authorizer=authorizer)

        CfnOutput(self, "ApiDomain",
                  value=f"{http_api.http_api_id}.execute-api.{region}.amazonaws.com")
        CfnOutput(self, "RouterFnName", value=fn.function_name)
