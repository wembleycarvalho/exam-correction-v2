"""
stack.py - all inference-demo infrastructure in a SINGLE CDK stack:

  Cognito
    Two responsibilities in one User Pool:
      1. Gateway auth (machine-to-machine): a Resource Server + App Client with
         the client_credentials flow and a secret stored in Secrets Manager.
         Used by the backend to obtain an OAuth token to call the Gateway.
      2. Frontend auth (interactive users): a second App Client wired to the
         Cognito Hosted UI using the Authorization Code + PKCE flow (public
         client, no secret). The SPA redirects users to Cognito to sign in and
         receives an access token that it forwards to the backend.

  AgentCore Gateway + inference target
    MCP Gateway with JWT authorization (Cognito). The inference target
    (zero-config "bedrock-mantle" connector) is created by a CUSTOM RESOURCE
    (a boto3 Lambda), because the CloudFormation type
    AWS::BedrockAgentCore::GatewayTarget does NOT yet model
    targetConfiguration.inference (only Http/Mcp). See
    custom_resources/inference_target/handler.py for details.

  Backend (Fargate)
    A single Fargate service (1 task, FastAPI with SSE streaming) behind an
    INTERNAL ALB (no public IP). Why Fargate and not Lambda? Token-by-token
    streaming over SSE needs a long-lived process; Lambda with the Python
    runtime has no native response-streaming support. The backend validates
    the user's Cognito access token before serving the protected endpoints.

  Frontend
    A PRIVATE S3 bucket served through CloudFront with Origin Access Control.

  CloudFront
    One distribution: default -> S3 (SPA), /api/* -> the internal ALB via a
    CloudFront VPC Origin (the ALB is never exposed to the internet; only
    CloudFront reaches it, inside the VPC).
"""

import os
from pathlib import Path

from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput, CustomResource, BundlingOptions,
    aws_cognito as cognito,
    aws_bedrockagentcore as bac,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    aws_elasticloadbalancingv2 as elbv2,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_secretsmanager as secretsmanager,
    custom_resources as cr,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parents[2]  # .../inference-demo
GATEWAY_NAME = "InferenceDemoGatewayV2"
OAUTH_SCOPE_NAME = "invoke"
RESOURCE_SERVER_ID = "inference-gateway"
CONNECTOR_ID = "bedrock-mantle"
# Scopes requested by the frontend during the Hosted UI login (Authorization
# Code + PKCE). These are standard OpenID Connect scopes.
FRONTEND_SCOPES = "openid email profile"


class InferenceDemoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------ Cognito ---
        user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="inference-demo-gateway-pool",
            # Interactive users sign in with their email address. Self sign-up
            # is disabled: users are created by an administrator (see README),
            # so the frontend is not open to anyone who finds the URL.
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        resource_server = cognito.UserPoolResourceServer(
            self, "ResourceServer",
            user_pool=user_pool,
            identifier=RESOURCE_SERVER_ID,
            scopes=[cognito.ResourceServerScope(
                scope_name=OAUTH_SCOPE_NAME,
                scope_description="Invoke the inference demo gateway",
            )],
        )
        full_scope_name = f"{RESOURCE_SERVER_ID}/{OAUTH_SCOPE_NAME}"

        # Machine-to-machine client (client_credentials) used by the backend to
        # obtain the OAuth token it sends to the Gateway.
        user_pool_client = cognito.UserPoolClient(
            self, "GatewayClient",
            user_pool=user_pool,
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[cognito.OAuthScope.resource_server(resource_server,
                        cognito.ResourceServerScope(scope_name=OAUTH_SCOPE_NAME,
                                                     scope_description="invoke"))],
            ),
        )
        user_pool_client.node.add_dependency(resource_server)

        domain = cognito.UserPoolDomain(
            self, "UserPoolDomain",
            user_pool=user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"inference-demo-{self.account}",
            ),
        )
        hosted_ui_base_url = (
            f"https://{domain.domain_name}.auth.{self.region}.amazoncognito.com"
        )

        client_secret_secret = secretsmanager.Secret(
            self, "ClientSecret",
            secret_string_value=user_pool_client.user_pool_client_secret,
            removal_policy=RemovalPolicy.DESTROY,
        )

        token_endpoint = f"{hosted_ui_base_url}/oauth2/token"
        discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/"
            f"{user_pool.user_pool_id}/.well-known/openid-configuration"
        )

        # ------------------------------------------------------------- Gateway --
        gateway_role = iam.Role(
            self, "GatewayRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn":
                                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*"},
                },
            ),
        )
        # bedrock-mantle is the internal service the zero-config connector uses
        # (not the classic bedrock:InvokeModel API). We keep the
        # bedrock:InvokeModel* fallback as well, just in case.
        gateway_role.add_to_policy(iam.PolicyStatement(
            sid="BedrockMantleInferenceConnector",
            actions=["bedrock-mantle:*"],
            resources=[
                f"arn:aws:bedrock-mantle:*:{self.account}:project/*",
                f"arn:aws:bedrock-mantle:*:{self.account}:project/default",
            ],
        ))
        # Custom provider targets (OpenAI/Gemini direct) authenticate with an
        # API key from the AgentCore Identity token vault; the Gateway retrieves
        # it at inference time via the API_KEY credential provider.
        gateway_role.add_to_policy(iam.PolicyStatement(
            sid="AgentCoreApiKeyVault",
            actions=[
                "bedrock-agentcore:GetResourceApiKey",
                "bedrock-agentcore:GetResourceOauth2Token",
                "bedrock-agentcore:GetWorkloadAccessToken",
                "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
            ],
            resources=["*"],
        ))
        # The API_KEY credential provider is backed by a Secrets Manager secret;
        # the Gateway reads it at inference time to inject the outbound key.
        gateway_role.add_to_policy(iam.PolicyStatement(
            sid="ReadIdentityApiKeySecrets",
            actions=["secretsmanager:GetSecretValue"],
            resources=[f"arn:aws:secretsmanager:*:{self.account}:secret:bedrock-agentcore*"],
        ))
        gateway_role.add_to_policy(iam.PolicyStatement(
            sid="BedrockInvokeFallback",
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
                f"arn:aws:bedrock:*:{self.account}:application-inference-profile/*",
            ],
        ))

        gateway = bac.CfnGateway(
            self, "Gateway",
            name=GATEWAY_NAME,
            role_arn=gateway_role.role_arn,
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=bac.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bac.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=discovery_url,
                    allowed_clients=[user_pool_client.user_pool_client_id],
                    allowed_scopes=[full_scope_name],
                ),
            ),
            protocol_type="MCP",
            protocol_configuration=bac.CfnGateway.GatewayProtocolConfigurationProperty(
                mcp=bac.CfnGateway.MCPGatewayConfigurationProperty(
                    search_type="SEMANTIC",
                ),
            ),
        )

        # ------------------------------------------- inference target (custom) --
        # See custom_resources/inference_target/handler.py: the CloudFormation
        # type does not yet model targetConfiguration.inference, so we use a
        # thin boto3 Lambda as a Custom Resource.
        cr_fn = lambda_.Function(
            self, "InferenceTargetHandler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.on_event",
            # Bundle an up-to-date boto3 (the runtime's built-in botocore is too
            # old to know the "inference" target format - it only accepts "mcp").
            # Requires Docker at deploy time (already needed for the backend image).
            code=lambda_.Code.from_asset(
                str(ROOT / "infra/inference_infra/custom_resources/inference_target"),
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && "
                        "cp -au . /asset-output",
                    ],
                ),
            ),
            timeout=Duration.seconds(60),
        )
        cr_fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "bedrock-agentcore:CreateGatewayTarget",
                "bedrock-agentcore:DeleteGatewayTarget",
                "bedrock-agentcore:GetGatewayTarget",
                "bedrock-agentcore:UpdateGatewayTarget",
                "bedrock-agentcore:ListGatewayTargets",
                # CreateGatewayTarget internally synchronizes the gateway's
                # targets, which requires this extra action.
                "bedrock-agentcore:SynchronizeGatewayTargets",
            ],
            resources=["*"],
        ))
        provider = cr.Provider(self, "InferenceTargetProvider", on_event_handler=cr_fn)
        inference_target = CustomResource(
            self, "InferenceTarget",
            service_token=provider.service_token,
            properties={
                "GatewayIdentifier": gateway.attr_gateway_identifier,
                "TargetName": "bedrock-inference",
                "ConnectorId": CONNECTOR_ID,
            },
        )
        inference_target.node.add_dependency(gateway_role)

        gateway_inference_base_url = (
            f"https://{gateway.attr_gateway_identifier}.gateway.bedrock-agentcore."
            f"{self.region}.amazonaws.com/inference/v1"
        )

        # -------------------------------------------------------- VPC + Fargate -
        # Two modes, to cope with the "max VPCs per region" limit:
        #
        #   1. Reuse an existing VPC: pass its id via CDK context
        #      (`npx cdk deploy -c vpcId=vpc-0123...`) or the EXISTING_VPC_ID
        #      env var. The VPC must have private subnets WITH egress (a NAT
        #      Gateway or the relevant VPC endpoints) across at least 2 AZs, so
        #      the Fargate tasks can reach ECR/Secrets Manager/Cognito/Gateway.
        #      Use `infra/list-vpcs.sh` to inspect candidates and the quota.
        #
        #   2. Create a new VPC (default): 2 AZs, 1 NAT Gateway. The NAT has a
        #      cost (~US$0.045/h + data); see the README for the VPC-endpoints
        #      alternative if you want to remove the NAT. This fails if the
        #      account already hit the VPC-per-region limit.
        existing_vpc_id = (
            self.node.try_get_context("vpcId") or os.environ.get("EXISTING_VPC_ID")
        )
        if existing_vpc_id:
            vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=existing_vpc_id)
        else:
            vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=1)

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        # An ALB must have exactly ONE subnet per Availability Zone. A VPC
        # created by CDK already satisfies this, but an imported VPC may have
        # multiple private subnets per AZ - which makes the ALB fail with
        # "cannot be attached to multiple subnets in the same AZ". So we pick
        # one private-with-egress subnet per AZ explicitly and build the
        # (internal) ALB ourselves, then hand it to the Fargate pattern.
        _private = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        _seen_azs: set[str] = set()
        alb_subnets: list = []
        for _subnet in _private.subnets:
            if _subnet.availability_zone not in _seen_azs:
                _seen_azs.add(_subnet.availability_zone)
                alb_subnets.append(_subnet)

        backend_lb = elbv2.ApplicationLoadBalancer(
            self, "BackendLB",
            vpc=vpc,
            internet_facing=False,  # INTERNAL ALB - no public IP
            vpc_subnets=ec2.SubnetSelection(subnets=alb_subnets),
        )

        # The COGNITO_APP_CLIENT_ID / COGNITO_USER_POOL_ID env vars are added
        # AFTER the frontend client is created (see add_environment below),
        # to avoid a circular reference (TaskDef -> FrontendClient ->
        # Distribution -> ALB).
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "BackendService",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            load_balancer=backend_lb,   # our internal ALB with one subnet per AZ
            listener_port=80,
            # Do NOT open the listener to 0.0.0.0/0. The ALB is reachable only
            # through the CloudFront VPC Origin; a custom resource (below) locks
            # its security group to the CloudFront-managed origin SG.
            open_listener=False,
            # Build and run on ARM64/Graviton. The image is pinned to LINUX_ARM64
            # below, so the Fargate runtime platform must match (otherwise the
            # container fails with an exec-format error and the circuit breaker
            # trips). ARM64 also builds natively on Apple Silicon and is cheaper.
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            # Place tasks in private subnets with egress (can span multiple
            # subnets per AZ - only the ALB requires one-per-AZ).
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            # Fail fast (and roll back) if a new task can't start, instead of
            # letting CloudFormation retry for up to ~3 hours.
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            # Keep the old task serving until the new one is healthy (with the
            # default max of 200%, this gives a zero-downtime rolling update
            # even at desired_count=1).
            min_healthy_percent=100,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(
                    str(ROOT / "backend"),
                    platform=ecr_assets.Platform.LINUX_ARM64,
                ),
                container_port=8000,
                environment={
                    "GATEWAY_INFERENCE_BASE_URL": gateway_inference_base_url,
                    "COGNITO_TOKEN_ENDPOINT": token_endpoint,
                    "COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id,
                    "COGNITO_CLIENT_SECRET_ARN": client_secret_secret.secret_arn,
                    "COGNITO_SCOPE": full_scope_name,
                    "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                    "AWS_REGION": self.region,
                },
            ),
        )
        fargate_service.target_group.configure_health_check(path="/api/health")
        client_secret_secret.grant_read(fargate_service.task_definition.task_role)

        # ----------------------------------------- S3: evaluation history ------
        # Private bucket holding Evaluation runs (interactive judge results) and
        # the datasets/outputs of async Bedrock Evaluations jobs. Never exposed:
        # only the Mantle Lambda (behind CloudFront + Cognito) reads/writes it.
        eval_bucket = s3.Bucket(
            self, "EvalBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        # Service role that Amazon Bedrock Evaluations assumes to run async
        # model-as-judge jobs: it reads the dataset + writes results in the eval
        # bucket, and invokes the (Bedrock-native) evaluator/judge model.
        eval_job_role = iam.Role(
            self, "EvalJobRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock.amazonaws.com",
                conditions={"StringEquals": {"aws:SourceAccount": self.account}},
            ),
        )
        eval_bucket.grant_read_write(eval_job_role)
        eval_job_role.add_to_policy(iam.PolicyStatement(
            sid="InvokeEvaluatorModels",
            actions=["bedrock:InvokeModel"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
            ],
        ))

        # -------------------------------------------- Mantle admin/obs Lambda ---
        # Separate service from the inference backend: powers the "Mantle-config"
        # tab (projects + CloudWatch observability) and the Inference tab's
        # project selector. Reachable ONLY via CloudFront (Function URL with
        # AWS_IAM + OAC) and validates the Cognito access token (passed in the
        # X-Cognito-Token header, since OAC overrides Authorization when signing).
        # Only needs COGNITO_USER_POOL_ID (user_pool is created early, so no
        # dependency cycle with the distribution).
        mantle_fn = lambda_.Function(
            self, "MantleApiHandler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            timeout=Duration.seconds(60),
            memory_size=256,
            code=lambda_.Code.from_asset(
                str(ROOT / "backend_mantle"),
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_13.bundling_image,
                    platform="linux/arm64",  # match the ARM64 function architecture
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && "
                        "cp -au . /asset-output",
                    ],
                ),
            ),
            environment={
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "EVAL_BUCKET": eval_bucket.bucket_name,
                "EVAL_ROLE_ARN": eval_job_role.role_arn,
                "GATEWAY_ID": gateway.attr_gateway_identifier,
            },
        )
        # Read/write the evaluation history bucket.
        eval_bucket.grant_read_write(mantle_fn)
        mantle_fn.add_to_role_policy(iam.PolicyStatement(
            sid="CloudWatchRead",
            actions=["cloudwatch:GetMetricData", "cloudwatch:ListMetrics"],
            resources=["*"],
        ))
        # Manage async Bedrock Evaluations jobs, and pass the eval service role.
        mantle_fn.add_to_role_policy(iam.PolicyStatement(
            sid="BedrockEvaluations",
            actions=["bedrock:CreateEvaluationJob", "bedrock:GetEvaluationJob",
                     "bedrock:ListEvaluationJobs", "bedrock:StopEvaluationJob"],
            resources=["*"],
        ))
        mantle_fn.add_to_role_policy(iam.PolicyStatement(
            sid="PassEvalRole", actions=["iam:PassRole"],
            resources=[eval_job_role.role_arn],
        ))
        # "Keys" tab: manage API Key Credential Providers (AgentCore Identity)
        # and the custom OpenAI/Gemini inference targets on the Gateway.
        # Broad bedrock-agentcore:* (scoped to this account's resources) because
        # the Identity credential-provider CRUD relies on several auxiliary
        # actions (token vault, workload identity) whose exact names vary; this
        # matches the pragmatic bedrock-mantle:* grant used elsewhere.
        mantle_fn.add_to_role_policy(iam.PolicyStatement(
            sid="AgentCoreIdentityAndTargets",
            actions=["bedrock-agentcore:*"],
            resources=["*"],
        ))
        # AgentCore Identity credential providers are backed by AWS Secrets
        # Manager (native integration): CreateApiKeyCredentialProvider creates a
        # secret in this account on the caller's behalf. Scope to the
        # AgentCore-owned "bedrock-agentcore*" secrets so this can't touch the
        # Cognito m2m client secret. No GetSecretValue: the Gateway reads the
        # key at runtime via its own role, not this Lambda.
        mantle_fn.add_to_role_policy(iam.PolicyStatement(
            sid="AgentCoreIdentitySecretsBacking",
            actions=[
                "secretsmanager:CreateSecret",
                "secretsmanager:PutSecretValue",
                "secretsmanager:UpdateSecret",
                "secretsmanager:TagResource",
                "secretsmanager:DescribeSecret",
                "secretsmanager:DeleteSecret",
                "secretsmanager:PutResourcePolicy",
                "secretsmanager:GetResourcePolicy",
                "secretsmanager:DeleteResourcePolicy",
            ],
            resources=[
                f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:bedrock-agentcore*",
            ],
        ))
        # The OpenAI-compatible mantle control APIs (projects, data retention)
        # authorize under the "bedrock-mantle:" service prefix (e.g.
        # bedrock-mantle:ListProjects) - the bearer token inherits this role's
        # permissions. The account-level data retention read is under "bedrock:".
        mantle_fn.add_to_role_policy(iam.PolicyStatement(
            sid="BedrockMantleAdmin",
            actions=["bedrock-mantle:*", "bedrock:GetAccountDataRetention",
                     "bedrock:PutAccountDataRetention", "bedrock:ListFoundationModels"],
            resources=["*"],
        ))
        mantle_fn_url = mantle_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
        )
        mantle_origin = origins.FunctionUrlOrigin.with_origin_access_control(
            mantle_fn_url,
            origin_access_control=cloudfront.FunctionUrlOriginAccessControl(
                self, "MantleOac", signing=cloudfront.Signing.SIGV4_ALWAYS,
            ),
        )

        # ------------------------------------------------------- S3 (frontend) --
        site_bucket = s3.Bucket(
            self, "SiteBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        # -------------------------------------------------------- CloudFront ----
        s3_origin = origins.S3BucketOrigin.with_origin_access_control(site_bucket)
        # VPC Origin: CloudFront reaches the ALB INSIDE the VPC (without the ALB
        # needing a public IP). The CDK manages the security group rules.
        alb_origin = origins.VpcOrigin.with_application_load_balancer(
            fargate_service.load_balancer,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
        )

        distribution = cloudfront.Distribution(
            self, "Distribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    # Forwards the Authorization header (user's bearer token) to
                    # the backend, minus the Host header.
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
                "/mantle/*": cloudfront.BehaviorOptions(
                    origin=mantle_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    # Forwards X-Cognito-Token (and other viewer headers) to the
                    # Lambda; OAC re-signs the Authorization header for SigV4.
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
        )

        site_url = f"https://{distribution.distribution_domain_name}"

        # Only this CloudFront distribution may invoke the Mantle Function URL.
        mantle_fn.add_permission(
            "AllowCloudFrontInvokeMantle",
            principal=iam.ServicePrincipal("cloudfront.amazonaws.com"),
            action="lambda:InvokeFunctionUrl",
            source_arn=(
                f"arn:aws:cloudfront::{self.account}:distribution/"
                f"{distribution.distribution_id}"
            ),
        )

        # ------------------------------------------ lock ALB SG to CloudFront ---
        # Restrict the internal ALB's security group to the CloudFront VPC Origin
        # only. Runs after the distribution so the CloudFront-managed VPC origin
        # SG already exists (see custom_resources/alb_sg_lock/handler.py).
        alb_sg_lock_fn = lambda_.Function(
            self, "AlbSgLockHandler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.on_event",
            code=lambda_.Code.from_asset(
                str(ROOT / "infra/inference_infra/custom_resources/alb_sg_lock")
            ),
            timeout=Duration.seconds(120),
        )
        alb_sg_lock_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ec2:DescribeSecurityGroups", "ec2:AuthorizeSecurityGroupIngress"],
            resources=["*"],
        ))
        alb_sg_lock_provider = cr.Provider(
            self, "AlbSgLockProvider", on_event_handler=alb_sg_lock_fn,
        )
        alb_sg_lock = CustomResource(
            self, "AlbSgLock",
            service_token=alb_sg_lock_provider.service_token,
            properties={
                "AlbSecurityGroupId": backend_lb.connections.security_groups[0].security_group_id,
                "VpcId": vpc.vpc_id,
            },
        )
        alb_sg_lock.node.add_dependency(distribution)

        # ------------------------------------------------- frontend login client -
        # Public client (no secret) for the interactive Hosted UI login using
        # the Authorization Code + PKCE flow. Created AFTER the distribution
        # because its callback/logout URLs point at the CloudFront domain.
        frontend_client = cognito.UserPoolClient(
            self, "FrontendClient",
            user_pool=user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[site_url, f"{site_url}/"],
                logout_urls=[site_url, f"{site_url}/"],
            ),
        )

        # Now that the frontend client exists, inject its id (and the pool id)
        # into the backend container so it can validate the user's access token.
        fargate_service.task_definition.default_container.add_environment(
            "COGNITO_APP_CLIENT_ID", frontend_client.user_pool_client_id,
        )

        # ------------------------------------------------------- deploy the SPA -
        # The static SPA has no build step, so the Cognito settings it needs at
        # runtime are injected as a config.json file generated at deploy time.
        s3_deploy.BucketDeployment(
            self, "DeploySite",
            sources=[
                s3_deploy.Source.asset(str(ROOT / "frontend")),
                s3_deploy.Source.json_data("config.json", {
                    "region": self.region,
                    "userPoolClientId": frontend_client.user_pool_client_id,
                    "cognitoDomain": hosted_ui_base_url,
                    "scope": FRONTEND_SCOPES,
                }),
            ],
            destination_bucket=site_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # ------------------------------------------------------------ outputs ---
        CfnOutput(self, "SiteUrl", value=site_url)
        CfnOutput(self, "GatewayId", value=gateway.attr_gateway_identifier)
        CfnOutput(self, "GatewayInferenceBaseUrl", value=gateway_inference_base_url)
        CfnOutput(self, "CognitoTokenEndpoint", value=token_endpoint)
        CfnOutput(self, "CognitoClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "CognitoScope", value=full_scope_name)
        CfnOutput(self, "CognitoHostedUiUrl", value=hosted_ui_base_url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "FrontendClientId", value=frontend_client.user_pool_client_id)
