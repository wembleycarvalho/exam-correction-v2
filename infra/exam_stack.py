"""Stack única (CDK) do Exam Correction v2.

Ordem: simplicidade → serverless → segurança → custo. Provisiona Cognito (sem
self-signup), S3 (FE via OAC + uploads), DynamoDB, SQS+DLQ, 2 Lambdas (IAM mínimo),
HTTP API + JWT authorizer, CloudFront (sem WAF — projeto de teste), Secrets Manager
(header de origem) e um parâmetro SSM para o ARN do AgentCore Runtime (deploy dos agentes).
"""
from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnParameter, CfnOutput, SecretValue,
    aws_cognito as cognito,
    aws_s3 as s3,
    aws_dynamodb as ddb,
    aws_sqs as sqs,
    aws_lambda as lambda_,
    aws_lambda_event_sources as sources,
    aws_secretsmanager as secrets,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as apigw_authz,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
)
from constructs import Construct

from modules.entrevistador import EntrevistadorModule
from modules.lms import LmsModule
from modules.orientador import OrientadorModule


class ExamStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)

        # Portal "A Arte do Possível WEB" — módulos selecionáveis via `-c modules=...`.
        # Fase atual: `correcao` (monolítico, ainda acoplado) + `entrevistador` (módulo próprio).
        # O desacoplamento das demos de correção em módulos vem numa fase seguinte.
        modules = {m.strip() for m in
                   (self.node.try_get_context("modules") or "correcao,entrevistador").split(",")
                   if m.strip()}

        worker_concurrency = int(self.node.try_get_context("workerConcurrency") or 5)
        default_model = self.node.try_get_context("defaultModelId") or ""
        model_pricing = self.node.try_get_context("modelPricing") or ""
        # Knowledge Base do módulo Provas Online. Provisionada por scripts/deploy-kb.sh
        # (acervo sintético de demonstração) e passada via contexto pelo deploy.sh.
        # Vazio = módulo Provas Online desabilitado (os demais fluxos seguem funcionando).
        kb_id = self.node.try_get_context("kbId") or ""
        kb_bucket = self.node.try_get_context("kbBucket") or ""

        origin_secret_param = CfnParameter(
            self, "OriginSecret", no_echo=True, min_length=16,
            description="Segredo compartilhado entre CloudFront e a API (gerado no deploy).",
        )

        # ---------------- Cognito (sem self-signup) ----------------
        user_pool = cognito.UserPool(
            self, "UserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)),
            password_policy=cognito.PasswordPolicy(
                min_length=12, require_lowercase=True, require_uppercase=True,
                require_digits=True, require_symbols=True),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
        )
        for grp in ("admin", "professor"):
            cognito.CfnUserPoolGroup(self, f"Group{grp.title()}",
                                     user_pool_id=user_pool.user_pool_id, group_name=grp)

        user_pool.add_domain(
            "HostedUiDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"exam-{self.account}"),
        )
        client = user_pool.add_client(
            "WebClient",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL,
                        cognito.OAuthScope.PROFILE],
                # Placeholders; deploy.sh atualiza com o domínio do CloudFront.
                callback_urls=["https://example.com/"],
                logout_urls=["https://example.com/"],
            ),
        )

        # ---------------- S3 ----------------
        fe_bucket = s3.Bucket(
            self, "FrontendBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        uploads_bucket = s3.Bucket(
            self, "UploadsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(90))],
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
                allowed_origins=["*"],  # deploy.sh restringe ao domínio do CloudFront
                allowed_headers=["*"], max_age=3000)],
        )

        # ---------------- DynamoDB ----------------
        def table(name, pk, sk=None):
            return ddb.Table(
                self, name,
                partition_key=ddb.Attribute(name=pk, type=ddb.AttributeType.STRING),
                sort_key=ddb.Attribute(name=sk, type=ddb.AttributeType.STRING) if sk else None,
                billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                encryption=ddb.TableEncryption.AWS_MANAGED,
                point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True),
                removal_policy=RemovalPolicy.RETAIN,
            )

        submissions = table("Submissions", "submissionId")
        submissions.add_global_secondary_index(
            index_name="byOwner",
            partition_key=ddb.Attribute(name="ownerId", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="createdAt", type=ddb.AttributeType.STRING))
        corrections = table("Corrections", "correctionId")
        corrections.add_global_secondary_index(
            index_name="bySubmission",
            partition_key=ddb.Attribute(name="submissionId", type=ddb.AttributeType.STRING))
        rubrics = table("Rubrics", "rubricId", "version")
        exams = table("Exams", "examId", "version")
        model_config = table("ModelConfig", "capability")
        test_registry = table("TestRegistry", "testId")

        # Provas Online: provas geradas (com gabarito) e tentativas respondidas.
        # Nomes explícitos (baixo volume, PK-only, scan+filter por ownerId).
        def named_table(name, table_name, pk):
            return ddb.Table(
                self, name, table_name=table_name,
                partition_key=ddb.Attribute(name=pk, type=ddb.AttributeType.STRING),
                billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                encryption=ddb.TableEncryption.AWS_MANAGED,
                point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=True),
                removal_policy=RemovalPolicy.RETAIN,
            )

        online_exams = named_table("OnlineExams", "exam-correction-v2-online-exams", "examId")
        online_attempts = named_table(
            "OnlineAttempts", "exam-correction-v2-online-attempts", "attemptId")

        # ---------------- SQS + DLQ ----------------
        dlq = sqs.Queue(self, "CorrectionDLQ", retention_period=Duration.days(14),
                        enforce_ssl=True)
        queue = sqs.Queue(
            self, "CorrectionQueue",
            visibility_timeout=Duration.minutes(15), enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=dlq),
        )

        # ---------------- Segredo de origem (CloudFront -> API) ----------------
        origin_secret = secrets.Secret(
            self, "OriginSecret2",
            secret_string_value=SecretValue.cfn_parameter(origin_secret_param))

        # ---------------- SSM: ARN do AgentCore Runtime ----------------
        runtime_arn_param = ssm.StringParameter(
            self, "AgentRuntimeArnParam",
            parameter_name=f"/{self.stack_name}/agent-runtime-arn",
            string_value="PENDING",
            description="ARN do AgentCore Runtime dos agentes (publicado pelo deploy-agents.sh).",
        )

        # ---------------- Lambdas ----------------
        common_env = {
            "SUBMISSIONS_TABLE": submissions.table_name,
            "CORRECTIONS_TABLE": corrections.table_name,
            "RUBRICS_TABLE": rubrics.table_name,
            "EXAMS_TABLE": exams.table_name,
            "MODEL_CONFIG_TABLE": model_config.table_name,
            "TEST_REGISTRY_TABLE": test_registry.table_name,
            "UPLOAD_BUCKET": uploads_bucket.bucket_name,
            "AGENT_RUNTIME_PARAM": runtime_arn_param.parameter_name,
            "METRICS_NAMESPACE": "ExamCorrection",
            "MODEL_PRICING": model_pricing,
            # Provas Online: tabelas (o worker corrige as tentativas → precisa delas).
            "ONLINE_EXAMS_TABLE": online_exams.table_name,
            "ONLINE_ATTEMPTS_TABLE": online_attempts.table_name,
        }
        api_env = {
            **common_env, "QUEUE_URL": queue.queue_url,
            "USER_POOL_ID": user_pool.user_pool_id,
            "ORIGIN_SECRET_ARN": origin_secret.secret_arn,
            # KB só é acessado pela API (geração + sugestão de estudo sob demanda).
            # Vazio quando o módulo Provas Online não foi provisionado.
            "KB_ID": kb_id, "KB_BUCKET": kb_bucket,
            "KB_THEMES_PREFIX": self.node.try_get_context("kbThemesPrefix")
            or "privado/graduacao/eng-software/",
        }
        code = lambda_.Code.from_asset("../avaliacao/backend")

        # Layer com boto3 recente (o boto3 do runtime Lambda pode não conhecer
        # o serviço `bedrock-agentcore` — necessário para InvokeAgentRuntime).
        boto3_layer = lambda_.LayerVersion(
            self, "Boto3Layer", code=lambda_.Code.from_asset("layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="boto3 recente (bedrock-agentcore data plane)",
        )
        # Layer com OpenCV (headless) + numpy p/ o OMR do cartão-resposta no worker.
        # Construída e publicada por scripts/build-omr-layer.sh (binários nativos grandes,
        # fora do repo) e passada por contexto (-c omrLayerArn). Ausente = OMR server-side
        # do cartão desabilitado (cv2 é importado de forma tardia); os demais fluxos seguem.
        omr_layer_arn = self.node.try_get_context("omrLayerArn") or ""
        worker_layers = [boto3_layer]
        if omr_layer_arn:
            worker_layers.append(lambda_.LayerVersion.from_layer_version_arn(
                self, "OmrLayer", omr_layer_arn))

        api_fn = lambda_.Function(
            self, "ApiFn", runtime=lambda_.Runtime.PYTHON_3_12,
            handler="api.handler.handler", code=code, timeout=Duration.seconds(30),
            memory_size=512, layers=[boto3_layer],
            environment=api_env,
        )
        worker_fn = lambda_.Function(
            self, "WorkerFn", runtime=lambda_.Runtime.PYTHON_3_12,
            handler="worker.handler.handler", code=code, timeout=Duration.minutes(10),
            memory_size=1024, reserved_concurrent_executions=worker_concurrency,
            layers=worker_layers, environment=common_env,
        )
        worker_fn.add_event_source(sources.SqsEventSource(
            queue, batch_size=1, report_batch_item_failures=True))

        # IAM mínimo
        for t in (submissions, corrections, rubrics, exams, model_config, test_registry,
                  online_exams, online_attempts):
            t.grant_read_write_data(api_fn)
        submissions.grant_read_write_data(worker_fn)
        corrections.grant_read_write_data(worker_fn)
        rubrics.grant_read_data(worker_fn)
        exams.grant_read_data(worker_fn)
        model_config.grant_read_data(worker_fn)
        online_exams.grant_read_data(worker_fn)          # correção assíncrona
        online_attempts.grant_read_write_data(worker_fn)  # grava resultado da tentativa
        uploads_bucket.grant_read_write(api_fn)
        uploads_bucket.grant_read(worker_fn)
        queue.grant_send_messages(api_fn)
        origin_secret.grant_read(api_fn)
        runtime_arn_param.grant_read(api_fn)
        runtime_arn_param.grant_read(worker_fn)

        # Invocar o AgentCore Runtime (worker sempre; api p/ wizard)
        invoke_runtime = iam.PolicyStatement(
            actions=["bedrock-agentcore:InvokeAgentRuntime"], resources=["*"])
        worker_fn.add_to_role_policy(invoke_runtime)
        api_fn.add_to_role_policy(invoke_runtime)
        # CloudWatch analytics + criação de usuários Cognito (admin)
        api_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["cloudwatch:GetMetricStatistics"], resources=["*"]))
        api_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:AdminCreateUser", "cognito-idp:AdminAddUserToGroup"],
            resources=[user_pool.user_pool_arn]))
        # Listar modelos multimodais para a Configuração de Modelos.
        api_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:ListFoundationModels", "bedrock:ListInferenceProfiles"],
            resources=["*"]))
        # Provas Online: recuperar passagens da Knowledge Base (RAG). Só a API acessa o KB
        # (geração das provas + sugestão de estudo sob demanda). O worker apenas corrige.
        # Concedido apenas quando o KB foi provisionado (evita ARN/recurso vazio).
        if kb_id:
            kb_arn = f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{kb_id}"
            api_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["bedrock:Retrieve"], resources=[kb_arn]))
        if kb_bucket:
            # Download das apostilas do KB (URL pré-assinada) + listagem p/ reindexar os temas.
            api_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:GetObject"], resources=[f"arn:aws:s3:::{kb_bucket}/*"]))
            api_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:ListBucket"], resources=[f"arn:aws:s3:::{kb_bucket}"]))

        # ---------------- HTTP API + JWT authorizer ----------------
        authorizer = apigw_authz.HttpUserPoolAuthorizer(
            "JwtAuthorizer", user_pool, user_pool_clients=[client])
        http_api = apigw.HttpApi(self, "HttpApi", create_default_stage=True)
        http_api.add_routes(
            path="/api/{proxy+}",
            methods=[apigw.HttpMethod.ANY],
            integration=integrations.HttpLambdaIntegration("ApiInteg", api_fn),
            authorizer=authorizer,
        )
        api_domain = f"{http_api.http_api_id}.execute-api.{self.region}.amazonaws.com"

        # ---------------- CloudFront ----------------
        # Sem WAF: projeto de teste. A borda segue protegida por header secreto de origem
        # (Secrets Manager) + JWT Cognito na API, e S3 via OAC + Block Public Access.
        security_headers = cloudfront.ResponseHeadersPolicy(
            self, "SecHeaders",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365), include_subdomains=True, override=True),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    # SAMEORIGIN (não DENY): o capítulo Entrevistador embute /entrevistador/
                    # via iframe de MESMA origem; DENY bloquearia qualquer enquadramento.
                    frame_option=cloudfront.HeadersFrameOption.SAMEORIGIN, override=True),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.SAME_ORIGIN, override=True),
            ),
        )
        api_origin = origins.HttpOrigin(
            api_domain,
            custom_headers={"x-origin-verify": origin_secret_param.value_as_string},
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
        )
        distribution = cloudfront.Distribution(
            self, "Distribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(fe_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=security_headers,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    response_headers_policy=security_headers,
                ),
            },
            error_responses=[cloudfront.ErrorResponse(
                http_status=403, response_http_status=200, response_page_path="/index.html")],
        )

        # ---------------- Módulo: Entrevistador Virtual (Fargate) ----------------
        # Serviço próprio de voz em tempo real, servido pelo MESMO CloudFront sob
        # /entrevistador/*. ALB protegido pelo header secreto (só aceita tráfego do CloudFront).
        if "entrevistador" in modules:
            entrevistador = EntrevistadorModule(
                self, "Entrevistador",
                origin_verify_secret=origin_secret_param.value_as_string,
            )
            distribution.add_behavior(
                "/entrevistador/*",
                origins.LoadBalancerV2Origin(
                    entrevistador.alb,
                    custom_headers={"x-origin-verify": origin_secret_param.value_as_string},
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                response_headers_policy=security_headers,
            )
            CfnOutput(self, "EntrevistadorAlbDns", value=entrevistador.alb.load_balancer_dns_name)

        # ---------------- Módulo: Orientador Acadêmico (Neptune + AgentCore) ----------------
        # Desacoplado do módulo de correção: HTTP API própria (bridge Lambda) servida pelo
        # mesmo CloudFront sob /orientador/* e protegida pelo mesmo Cognito.
        if "orientador" in modules:
            orientador = OrientadorModule(
                self, "Orientador", stack_name=self.stack_name,
                user_pool=user_pool, user_pool_client=client, boto3_layer=boto3_layer,
                model_id=self.node.try_get_context("orientadorModelId") or "amazon.nova-pro-v1:0",
            )
            distribution.add_behavior(
                "/orientador/*",
                origins.HttpOrigin(orientador.api_domain,
                                   protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                response_headers_policy=security_headers,
            )

        # ---------------- Módulo: LMS de Vídeo (Marengo + S3 Vectors) ----------------
        # Busca multimodal em vídeo. API sob /lms/* (HTTP API + JWT) e mídia sob /lms/media/*
        # (S3 privado via OAC). O índice S3 Vectors é criado fora do CDK (deploy-lms.sh).
        if "lms" in modules:
            lms = LmsModule(
                self, "Lms", stack_name=self.stack_name,
                user_pool=user_pool, user_pool_client=client, boto3_layer=boto3_layer,
                vector_bucket=self.node.try_get_context("lmsVectorBucket") or "",
                marengo_model_id=self.node.try_get_context("lmsMarengoModelId")
                or "twelvelabs.marengo-embed-3-0-v1:0",
            )
            distribution.add_behavior(
                "/lms/media/*",
                origins.S3BucketOrigin.with_origin_access_control(lms.media_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                response_headers_policy=security_headers,
            )
            distribution.add_behavior(
                "/lms/*",
                origins.HttpOrigin(lms.api_domain,
                                   protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                response_headers_policy=security_headers,
            )

        # ---------------- Outputs ----------------
        CfnOutput(self, "DistributionDomain", value=distribution.distribution_domain_name)
        CfnOutput(self, "DistributionId", value=distribution.distribution_id)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=client.user_pool_client_id)
        CfnOutput(self, "CognitoDomainPrefix", value=f"exam-{self.account}")
        CfnOutput(self, "FrontendBucketName", value=fe_bucket.bucket_name)
        CfnOutput(self, "UploadsBucketName", value=uploads_bucket.bucket_name)
        CfnOutput(self, "AgentRuntimeArnParamName", value=runtime_arn_param.parameter_name)
        CfnOutput(self, "Region", value=self.region)
