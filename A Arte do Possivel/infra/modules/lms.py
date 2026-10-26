"""Módulo LMS de Vídeo — busca multimodal (TwelveLabs Marengo Embed 3.0 + S3 Vectors).

Serverless e desacoplado (padrão dos módulos Entrevistador/Orientador): sem VPC (Bedrock,
S3, DynamoDB e S3 Vectors têm endpoints públicos). Duas Lambdas (API/busca e ingestão),
bucket S3 privado do acervo (servido pelo CloudFront via OAC sob /lms/media/*), tabelas
DynamoDB (catálogo + estado de ingestão) e HTTP API + Cognito JWT (sob /lms/*).

O índice **S3 Vectors** é criado FORA do CDK (ainda sem cobertura CloudFormation estável),
pelo scripts/deploy-lms.sh; aqui recebemos apenas o NOME do vector bucket para env + IAM.

Expõe `self.api_domain` (behavior /lms/*) e `self.media_bucket` (behavior /lms/media/*).
"""
from aws_cdk import (
    CfnOutput, Duration, RemovalPolicy, Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_authorizers as apigw_authz,
    aws_apigatewayv2_integrations as integrations,
    aws_dynamodb as ddb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
)
from constructs import Construct


class LmsModule(Construct):
    def __init__(self, scope: Construct, cid: str, *, stack_name: str, user_pool,
                 user_pool_client, boto3_layer, vector_bucket: str = "",
                 marengo_model_id: str = "twelvelabs.marengo-embed-3-0-v1:0",
                 vector_index: str = "lms-segments", **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)
        stack = Stack.of(self)

        # Nome do vector bucket (S3 Vectors) — criado pelo deploy-lms.sh. Default estável.
        vector_bucket = vector_bucket or f"{stack_name}-lms-vectors".lower()

        # --- S3: acervo de vídeo (privado; servido pelo CloudFront via OAC) ---
        media_bucket = s3.Bucket(
            self, "MediaBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.media_bucket = media_bucket

        # --- DynamoDB: catálogo (PK disc_id) + estado de ingestão (PK video) ---
        catalog_table = ddb.Table(
            self, "CatalogTable",
            partition_key=ddb.Attribute(name="disc_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            encryption=ddb.TableEncryption.AWS_MANAGED, removal_policy=RemovalPolicy.RETAIN,
        )
        ingest_table = ddb.Table(
            self, "IngestTable",
            partition_key=ddb.Attribute(name="video", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            encryption=ddb.TableEncryption.AWS_MANAGED, removal_policy=RemovalPolicy.RETAIN,
        )

        # --- Código das Lambdas (pacote lms/, sem testes) ---
        code = lambda_.Code.from_asset(
            "../lms", exclude=["tests", "conftest.py", "**/__pycache__", "*.pyc"])
        common_env = {
            "LMS_MARENGO_MODEL_ID": marengo_model_id,
            "LMS_VECTOR_BUCKET": vector_bucket,
            "LMS_VECTOR_INDEX": vector_index,
            "LMS_MEDIA_BUCKET": media_bucket.bucket_name,
            # mesmo path do behavior /lms/media/* -> chave S3 casa com a URL (sem reescrita)
            "LMS_MEDIA_PREFIX": "lms/media/",
            "LMS_EMBED_OUTPUT_PREFIX": "embeddings/",
            "LMS_CATALOG_TABLE": catalog_table.table_name,
            "LMS_INGEST_TABLE": ingest_table.table_name,
            "LMS_MEDIA_BASE_PATH": "/lms/media",
            "LMS_ACCOUNT_ID": stack.account,
            # Pegasus (fase 2): on-demand exige inference profile (cross-region).
            "LMS_PEGASUS_MODEL_ID": "us.twelvelabs.pegasus-1-2-v1:0",
            "LMS_PEGASUS_REGION": "us-east-1",
        }

        api_fn = lambda_.Function(
            self, "ApiFn", runtime=lambda_.Runtime.PYTHON_3_12, handler="api.handler.handler",
            code=code, timeout=Duration.seconds(60), memory_size=512, layers=[boto3_layer],
            environment=common_env,
        )
        ingest_fn = lambda_.Function(
            self, "IngestFn", runtime=lambda_.Runtime.PYTHON_3_12,
            handler="ingest.handler.handler", code=code, timeout=Duration.minutes(15),
            memory_size=1024, layers=[boto3_layer], environment=common_env,
        )

        # --- Permissões (privilégio mínimo) ---
        for fn in (api_fn, ingest_fn):
            media_bucket.grant_read_write(fn)  # ler vídeo + ler/escrever saída de embeddings
            # Bedrock: embeddings síncronos (texto/imagem) e assíncronos (vídeo/áudio) do Marengo.
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:StartAsyncInvoke",
                         "bedrock:GetAsyncInvoke", "bedrock:ListAsyncInvokes"],
                resources=[
                    f"arn:aws:bedrock:{stack.region}::foundation-model/{marengo_model_id}",
                    f"arn:aws:bedrock:{stack.region}:{stack.account}:async-invoke/*",
                ],
            ))
            # S3 Vectors: consulta/gravação no índice do módulo.
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["s3vectors:PutVectors", "s3vectors:QueryVectors",
                         "s3vectors:GetVectors", "s3vectors:ListVectors",
                         "s3vectors:DeleteVectors", "s3vectors:CreateIndex",
                         "s3vectors:GetIndex", "s3vectors:ListIndexes"],
                resources=[
                    f"arn:aws:s3vectors:{stack.region}:{stack.account}:bucket/{vector_bucket}",
                    f"arn:aws:s3vectors:{stack.region}:{stack.account}:bucket/{vector_bucket}/index/*",
                ],
            ))
        catalog_table.grant_read_write_data(ingest_fn)
        ingest_table.grant_read_write_data(ingest_fn)
        catalog_table.grant_read_data(api_fn)
        ingest_table.grant_read_data(api_fn)

        # Pegasus 1.2 (fase 2) — só a ApiFn (resumo/Q&A por vídeo). Base em us-west-2 +
        # perfil de inferência cross-region.
        api_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/twelvelabs.pegasus-*",
                f"arn:aws:bedrock:*:{stack.account}:inference-profile/*pegasus*",
            ],
        ))

        # --- HTTP API + Cognito (mesma auth do portal) ---
        authorizer = apigw_authz.HttpUserPoolAuthorizer(
            "LmsJwt", user_pool, user_pool_clients=[user_pool_client])
        http_api = apigw.HttpApi(self, "LmsApi", create_default_stage=True)
        integ = integrations.HttpLambdaIntegration("LmsInteg", api_fn)
        # Health público (sem JWT) — usado pela bateria de smoke/monitoramento, como o
        # /entrevistador/health. Rota exata tem precedência sobre o {proxy+}.
        http_api.add_routes(path="/lms/health", methods=[apigw.HttpMethod.GET], integration=integ)
        http_api.add_routes(
            path="/lms/{proxy+}", methods=[apigw.HttpMethod.ANY],
            integration=integ, authorizer=authorizer,
        )
        self.api_domain = f"{http_api.http_api_id}.execute-api.{stack.region}.amazonaws.com"

        # --- Outputs (para o deploy-lms.sh) ---
        def _out(cid_: str, key: str, value: str):
            o = CfnOutput(self, cid_, value=value)
            o.override_logical_id(key)

        _out("OutMediaBucket", "LmsMediaBucket", media_bucket.bucket_name)
        _out("OutVectorBucket", "LmsVectorBucket", vector_bucket)
        _out("OutVectorIndex", "LmsVectorIndex", vector_index)
        _out("OutCatalogTable", "LmsCatalogTable", catalog_table.table_name)
        _out("OutIngestTable", "LmsIngestTable", ingest_table.table_name)
        _out("OutIngestFn", "LmsIngestFn", ingest_fn.function_name)
        _out("OutApiId", "LmsApiId", http_api.http_api_id)
