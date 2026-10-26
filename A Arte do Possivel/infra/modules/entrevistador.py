"""Módulo Entrevistador Virtual — voz em tempo real (Amazon Nova Sonic).

Primeira demo que foge do serverless: servidor persistente (FastAPI + WebSocket) em
ECS Fargate, atrás de um ALB, servido pelo mesmo CloudFront do portal sob `/entrevistador/*`.

O ALB é internet-facing mas só aceita tráfego com o header secreto de origem injetado pelo
CloudFront (mesmo padrão da API) — nada acessível fora do CloudFront.
"""
from aws_cdk import (
    Duration, RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as ecr_assets,
    aws_dynamodb as ddb,
    aws_s3 as s3,
)
from constructs import Construct


class EntrevistadorModule(Construct):
    """Cria VPC (sem NAT), ECS Fargate (ARM64), ALB protegido por header de origem.

    Expõe `self.alb` para o portal registrar o behavior `/entrevistador/*` no CloudFront.
    """

    def __init__(self, scope: Construct, cid: str, *, origin_verify_secret: str,
                 model_id: str = "amazon.nova-2-sonic-v1:0", voice_id: str = "carolina",
                 **kwargs) -> None:
        super().__init__(scope, cid, **kwargs)

        # Usa a VPC default da conta (evita estourar a quota de VPCs e não cria NAT).
        # As tasks ficam em subnets públicas com IP público (egress ao Bedrock via IGW);
        # o SG restringe o ingresso apenas ao ALB.
        vpc = ec2.Vpc.from_lookup(self, "Vpc", is_default=True)

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights=True)

        # Tabela de vagas do entrevistador (criadas + semeadas; todas gerenciáveis).
        vagas_table = ddb.Table(
            self, "VagasTable",
            partition_key=ddb.Attribute(name="vagaId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            encryption=ddb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Histórico de entrevistas (relatório + transcrição). RETAIN para não perder
        # os resultados a cada deploy — antes eram HTMLs no disco efêmero do container.
        reports_table = ddb.Table(
            self, "ReportsTable",
            partition_key=ddb.Attribute(name="reportId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            encryption=ddb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Avatares gerenciáveis: metadados/calibração em DynamoDB, imagens em S3 privado
        # (servidas pelo container via API — o browser nunca fala direto com o S3).
        avatars_table = ddb.Table(
            self, "AvatarsTable",
            partition_key=ddb.Attribute(name="avatarId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            encryption=ddb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
        )
        avatars_bucket = s3.Bucket(
            self, "AvatarsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Role da task: Nova Sonic (streaming bidirecional) + Nova Lite (relatório/geração).
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        vagas_table.grant_read_write_data(task_role)
        reports_table.grant_read_write_data(task_role)
        avatars_table.grant_read_write_data(task_role)
        avatars_bucket.grant_read_write(task_role)
        task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModelWithBidirectionalStream",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:InvokeModel",
            ],
            resources=[
                "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                "arn:aws:bedrock:*:*:inference-profile/*nova*",
                # Geração de avatar (Stability Image) — cross-region (us-west-2).
                "arn:aws:bedrock:*::foundation-model/stability.*",
            ],
        ))

        task_def = ecs.FargateTaskDefinition(
            self, "TaskDef", cpu=512, memory_limit_mib=1024, task_role=task_role,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX),
        )
        task_def.add_container(
            "Container",
            image=ecs.ContainerImage.from_asset(
                "../interviewer", platform=ecr_assets.Platform.LINUX_ARM64),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="entrevistador",
                log_retention=logs.RetentionDays.TWO_WEEKS),
            environment={
                "PORT": "8080", "BASE_PATH": "/entrevistador",
                "MODEL_ID": model_id, "VOICE_ID": voice_id,
                "VAGAS_TABLE": vagas_table.table_name,
                "REPORTS_TABLE": reports_table.table_name,
                "AVATARS_TABLE": avatars_table.table_name,
                "AVATARS_BUCKET": avatars_bucket.bucket_name,
                # Stable Image Ultra tem melhor qualidade p/ retrato; só existe fora de
                # us-east-1, então chamamos cross-region. Ambos retornam images:[base64].
                "IMAGE_MODEL_ID": "stability.stable-image-ultra-v1:1",
                "IMAGE_MODEL_REGION": "us-west-2",
            },
            port_mappings=[ecs.PortMapping(container_port=8080)],
        )

        # Security groups: ALB aberto (80) → tasks só aceitam do ALB (8080).
        alb_sg = ec2.SecurityGroup(self, "AlbSg", vpc=vpc, allow_all_outbound=True)
        alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP do CloudFront")
        svc_sg = ec2.SecurityGroup(self, "SvcSg", vpc=vpc, allow_all_outbound=True)
        svc_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(8080), "Somente via ALB")

        service = ecs.FargateService(
            self, "Service", cluster=cluster, task_definition=task_def,
            desired_count=1, assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[svc_sg],
            min_healthy_percent=0,  # 1 task só (demo): permite substituição sem 2ª task
        )

        self.alb = elbv2.ApplicationLoadBalancer(
            self, "Alb", vpc=vpc, internet_facing=True, security_group=alb_sg)
        listener = self.alb.add_listener(
            "Listener", port=80,
            default_action=elbv2.ListenerAction.fixed_response(
                403, content_type="text/plain", message_body="Forbidden"),
        )
        tg = elbv2.ApplicationTargetGroup(
            self, "Tg", vpc=vpc, port=8080, protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP, targets=[service],
            health_check=elbv2.HealthCheck(
                path="/entrevistador/health", healthy_http_codes="200",
                interval=Duration.seconds(30)),
            deregistration_delay=Duration.seconds(10),
        )
        # Só encaminha ao serviço se vier o header secreto do CloudFront.
        listener.add_action(
            "AllowFromCloudFront", priority=1,
            conditions=[elbv2.ListenerCondition.http_header(
                "x-origin-verify", [origin_verify_secret])],
            action=elbv2.ListenerAction.forward([tg]),
        )
