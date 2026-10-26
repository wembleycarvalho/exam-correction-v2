"""
stack.py - all of websearch-demo's infra in ONE CDK stack:

  Cognito (two separate app clients on the same User Pool/domain)
    - GatewayClient: client_credentials, secret in Secrets Manager. Used by
      the Lambda to authenticate to the AgentCore Gateway (M2M).
    - LoginClient: authorization_code + PKCE, public (no secret). Used by
      end users to sign in via the Hosted UI (browser redirect).
    A Resource Server (scope websearch-gateway/invoke) backs the M2M scope.

  AgentCore Gateway + Target
    MCP Gateway with JWT authorization (Cognito) and a GatewayTarget of type
    native "web-search" connector (100% managed by AWS: no Lambda, no API
    key).

  Backend
    A Lambda (backend/handler.py) behind a Function URL protected by
    IAM + Origin Access Control (only CloudFront can invoke it). Handles:
      - GET  /api/auth/config  -> public Hosted UI config for the frontend
      - POST /api/auth/token   -> proxies the PKCE code/token exchange to
                                   Cognito (avoids relying on Cognito's
                                   /oauth2/token CORS behavior, which is
                                   undocumented/inconsistent for browsers)
      - POST /api/search       -> validates the user's access token, then
                                   calls the Gateway using the M2M client

  Frontend
    PRIVATE S3 bucket (no website hosting, no public access) served via
    CloudFront with Origin Access Control. The SPA redirects unauthenticated
    users to the Cognito Hosted UI (real browser navigation, not fetch/XHR -
    this is the pattern Cognito actually supports for login/logout).

  CloudFront
    A single distribution: default behavior -> S3 (SPA), /api/* -> the
    Lambda Function URL. Same origin = no CORS to configure on the frontend.

Why everything in one stack? It's a small demo (2 resource types: Gateway +
target). There's no reason to split into multiple/nested stacks - that would
only add complexity without real benefit here.
"""

from pathlib import Path

from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_cognito as cognito,
    aws_bedrockagentcore as bac,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    custom_resources as cr,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parents[2]  # .../websearch-demo
GATEWAY_NAME = "WebSearchDemoGateway"
OAUTH_SCOPE_NAME = "invoke"
RESOURCE_SERVER_ID = "websearch-gateway"


class WebSearchDemoStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------ Cognito ---
        user_pool = cognito.UserPool(
            self, "UserPool",
            user_pool_name="websearch-demo-gateway-pool",
            # Self sign-up is DISABLED: users can't register themselves via the
            # Hosted UI. Accounts are created by an admin (see the
            # create-admin-user.sh script / README).
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            removal_policy=RemovalPolicy.DESTROY,
        )
        resource_server = cognito.UserPoolResourceServer(
            self, "ResourceServer",
            user_pool=user_pool,
            identifier=RESOURCE_SERVER_ID,
            scopes=[cognito.ResourceServerScope(
                scope_name=OAUTH_SCOPE_NAME,
                scope_description="Invoke the WebSearch demo gateway",
            )],
        )
        full_scope_name = f"{RESOURCE_SERVER_ID}/{OAUTH_SCOPE_NAME}"

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
                domain_prefix=f"websearch-demo-{self.account}",
            ),
        )

        # Placeholder callback/logout URLs. The real URL is the CloudFront
        # domain, which only exists after the Distribution is created - and
        # the Distribution depends on the Lambda, which depends on this login
        # client (for COGNITO_LOGIN_CLIENT_ID). Referencing the distribution
        # domain directly here would create a circular dependency
        # (LoginClient -> Distribution -> Lambda -> LoginClient). So we set a
        # placeholder now and patch the URLs via a custom resource at the end
        # (nothing depends on that custom resource, so it breaks the cycle).
        callback_urls = ["https://placeholder.example.com/"]

        # Public app client (no secret) for end-user sign-in via the Hosted
        # UI, using the Authorization Code + PKCE flow. This never talks to
        # the Gateway directly - it only proves who the user is.
        login_client = cognito.UserPoolClient(
            self, "LoginClient",
            user_pool=user_pool,
            generate_secret=False,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                # COGNITO_ADMIN = "aws.cognito.signin.user.admin": required so
                # the backend can validate the access token with the Cognito
                # GetUser API. Without it, GetUser rejects the token.
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.COGNITO_ADMIN,
                ],
                callback_urls=callback_urls,
                logout_urls=callback_urls,
            ),
            prevent_user_existence_errors=True,
        )

        # Store the client_secret in Secrets Manager (never in a plaintext
        # environment variable or in code). The Lambda reads it at runtime.
        client_secret_secret = secretsmanager.Secret(
            self, "ClientSecret",
            secret_string_value=user_pool_client.user_pool_client_secret,
            removal_policy=RemovalPolicy.DESTROY,
        )

        cognito_base_url = f"https://{domain.domain_name}.auth.{self.region}.amazoncognito.com"
        token_endpoint = f"{cognito_base_url}/oauth2/token"
        authorize_endpoint = f"{cognito_base_url}/oauth2/authorize"
        logout_endpoint = f"{cognito_base_url}/logout"
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
        # Minimal permissions required by the native Web Search Tool connector.
        gateway_role.add_to_policy(iam.PolicyStatement(
            sid="InvokeGateway",
            actions=["bedrock-agentcore:InvokeGateway"],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*"],
        ))
        gateway_role.add_to_policy(iam.PolicyStatement(
            sid="InvokeWebSearch",
            actions=["bedrock-agentcore:InvokeWebSearch"],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:aws:tool/web-search.v1"],
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

        # MCP target: native "web-search" connector (managed by AWS).
        # No API key, no Lambda: the Gateway authenticates to the backend
        # with its OWN service role above (credentialProviderType=GATEWAY_IAM_ROLE).
        websearch_target = bac.CfnGatewayTarget(
            self, "WebSearchTarget",
            gateway_identifier=gateway.attr_gateway_identifier,
            name="websearch",
            target_configuration=bac.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bac.CfnGatewayTarget.McpTargetConfigurationProperty(
                    connector=bac.CfnGatewayTarget.ConnectorTargetConfigurationProperty(
                        source=bac.CfnGatewayTarget.ConnectorSourceProperty(
                            connector_id="web-search",
                        ),
                        configurations=[bac.CfnGatewayTarget.ConnectorConfigurationProperty(
                            name="WebSearch",
                            parameter_values={},
                        )],
                    ),
                ),
            ),
            credential_provider_configurations=[
                bac.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                ),
            ],
        )
        websearch_target.node.add_dependency(gateway_role)

        gateway_mcp_url = (
            f"https://{gateway.attr_gateway_identifier}.gateway.bedrock-agentcore."
            f"{self.region}.amazonaws.com/mcp"
        )
        # tool name namespaced by the Gateway: "<targetName>___<toolName>"
        websearch_tool_name = "websearch___WebSearch"

        # ------------------------------------------------------------- Lambda ---
        backend_fn = lambda_.Function(
            self, "SearchFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(ROOT / "backend")),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "GATEWAY_MCP_URL": gateway_mcp_url,
                "WEBSEARCH_TOOL_NAME": websearch_tool_name,
                "COGNITO_TOKEN_ENDPOINT": token_endpoint,
                "COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id,
                "COGNITO_CLIENT_SECRET_ARN": client_secret_secret.secret_arn,
                "COGNITO_SCOPE": full_scope_name,
                # User-facing login (Hosted UI, PKCE) - separate client, no secret.
                "COGNITO_LOGIN_CLIENT_ID": login_client.user_pool_client_id,
                "COGNITO_AUTHORIZE_ENDPOINT": authorize_endpoint,
                "COGNITO_LOGOUT_ENDPOINT": logout_endpoint,
            },
        )
        client_secret_secret.grant_read(backend_fn)
        # The Lambda invokes the Gateway as a CLIENT (via a Cognito JWT token),
        # not as the Gateway itself - no extra IAM permission is needed here.
        # The end user's access token is validated with cognito-idp:GetUser,
        # which Cognito accepts as a bearer-token call - no IAM permission
        # needed (Cognito doesn't evaluate IAM policies for this operation).

        fn_url = backend_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
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
        api_origin = origins.FunctionUrlOrigin.with_origin_access_control(
            fn_url,
            origin_access_control=cloudfront.FunctionUrlOriginAccessControl(
                self, "ApiOac",
                signing=cloudfront.Signing.SIGV4_ALWAYS,
            ),
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
                    origin=api_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
        )
        # Allows ONLY this distribution to invoke the Function URL.
        backend_fn.add_permission(
            "AllowCloudFrontInvoke",
            principal=iam.ServicePrincipal("cloudfront.amazonaws.com"),
            action="lambda:InvokeFunctionUrl",
            source_arn=(
                f"arn:aws:cloudfront::{self.account}:distribution/"
                f"{distribution.distribution_id}"
            ),
        )

        s3_deploy.BucketDeployment(
            self, "DeploySite",
            sources=[s3_deploy.Source.asset(str(ROOT / "frontend"))],
            destination_bucket=site_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # Now that the distribution's domain is known, point the login
        # client's callback/logout URLs at the real site. Done via a custom
        # resource (not a direct CFN reference) to avoid the circular
        # dependency LoginClient -> Distribution -> Lambda -> LoginClient.
        # Nothing depends on this resource, so it sits "outside" the cycle.
        #
        # NOTE: updateUserPoolClient is a FULL replace, so we must restate the
        # whole OAuth config here - otherwise Cognito resets the omitted
        # fields to defaults (which would break the PKCE login flow).
        site_url = f"https://{distribution.distribution_domain_name}/"
        _update_call = cr.AwsSdkCall(
            service="CognitoIdentityServiceProvider",
            action="updateUserPoolClient",
            parameters={
                "UserPoolId": user_pool.user_pool_id,
                "ClientId": login_client.user_pool_client_id,
                "CallbackURLs": [site_url],
                "LogoutURLs": [site_url],
                "AllowedOAuthFlows": ["code"],
                "AllowedOAuthFlowsUserPoolClient": True,
                "AllowedOAuthScopes": ["openid", "email", "aws.cognito.signin.user.admin"],
                "SupportedIdentityProviders": ["COGNITO"],
                "PreventUserExistenceErrors": "ENABLED",
            },
            physical_resource_id=cr.PhysicalResourceId.of(
                f"UpdateLoginClientUrls-{login_client.user_pool_client_id}"
            ),
        )
        update_login_urls = cr.AwsCustomResource(
            self, "UpdateLoginClientUrls",
            on_create=_update_call,
            on_update=_update_call,
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[user_pool.user_pool_arn],
            ),
            # updateUserPoolClient is in the Lambda runtime's built-in AWS SDK,
            # so don't npm-install the latest SDK at deploy time (avoids the
            # slower/network-dependent install and silences the CDK warning).
            install_latest_aws_sdk=False,
        )
        # Make the update run after both prerequisites exist.
        update_login_urls.node.add_dependency(login_client)
        update_login_urls.node.add_dependency(distribution)

        # ------------------------------------------------------------ outputs ---
        CfnOutput(self, "SiteUrl", value=site_url)
        CfnOutput(self, "GatewayId", value=gateway.attr_gateway_identifier)
        CfnOutput(self, "GatewayMcpUrl", value=gateway_mcp_url)
        CfnOutput(self, "CognitoTokenEndpoint", value=token_endpoint)
        CfnOutput(self, "CognitoClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "CognitoScope", value=full_scope_name)
        CfnOutput(self, "CognitoLoginClientId", value=login_client.user_pool_client_id)
        CfnOutput(self, "CognitoHostedUiDomain", value=cognito_base_url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
