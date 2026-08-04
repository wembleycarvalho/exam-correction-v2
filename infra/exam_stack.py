"""Stack única (CDK) do Exam Correction v2.

Ordem: simplicidade → serverless → segurança → custo. Provisiona Cognito (sem
self-signup), S3 (FE via OAC + uploads), DynamoDB, SQS+DLQ, 2 Lambdas (IAM mínimo),
HTTP API + JWT authorizer, CloudFront + WAF, Secrets Manager (header de origem) e um
parâmetro SSM para o ARN do AgentCore Runtime (publicado pelo deploy dos agentes).
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
    aws_wafv2 as wafv2,
)
from constructs import Construct


class ExamStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)

        worker_concurrency = int(self.node.try_get_context("workerConcurrency") or 5)
        default_model = self.node.try_get_context("defaultModelId") or ""
        model_pricing = self.node.try_get_context("modelPricing") or ""
        # Knowledge Base (conteúdo já embedado) usada pelo módulo Provas Online.
        kb_id = self.node.try_get_context("kbId") or "L2KOGGTB6K"
        kb_bucket = self.node.try_get_context("kbBucket") or "kb-vestibular-demo-831782568328"

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
            "KB_ID": kb_id, "KB_BUCKET": kb_bucket,
            "KB_THEMES_PREFIX": "privado/graduacao/eng-software/",
        }
        code = lambda_.Code.from_asset("../backend")

        # Layer com boto3 recente (o boto3 do runtime Lambda pode não conhecer
        # o serviço `bedrock-agentcore` — necessário para InvokeAgentRuntime).
        boto3_layer = lambda_.LayerVersion(
            self, "Boto3Layer", code=lambda_.Code.from_asset("layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="boto3 recente (bedrock-agentcore data plane)",
        )
        # Layer com OpenCV (headless) + numpy p/ o OMR do cartão-resposta no worker.
        # Construída e publicada por scripts/build-omr-layer.sh (binários nativos grandes,
        # fora do repo). Referenciada por ARN para não versionar ~190MB.
        omr_layer = lambda_.LayerVersion.from_layer_version_arn(
            self, "OmrLayer",
            "arn:aws:lambda:us-east-1:831782568328:layer:exam-omr-opencv:1",
        )

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
            layers=[boto3_layer, omr_layer], environment=common_env,
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
        kb_arn = f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{kb_id}"
        api_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:Retrieve"], resources=[kb_arn]))
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

        # ---------------- WAF (CLOUDFRONT scope; stack em us-east-1) ----------------
        web_acl = wafv2.CfnWebACL(
            self, "WebAcl", scope="CLOUDFRONT",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True, metric_name="examWebAcl", sampled_requests_enabled=True),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="Common", priority=1,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS", name="AWSManagedRulesCommonRuleSet")),
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True, metric_name="common", sampled_requests_enabled=True)),
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimit", priority=2,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=2000, aggregate_key_type="IP")),
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True, metric_name="rate", sampled_requests_enabled=True)),
            ],
        )

        # ---------------- CloudFront ----------------
        security_headers = cloudfront.ResponseHeadersPolicy(
            self, "SecHeaders",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365), include_subdomains=True, override=True),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY, override=True),
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
            web_acl_id=web_acl.attr_arn,
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
