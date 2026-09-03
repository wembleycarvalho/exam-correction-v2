"""Diagrama de arquitetura do módulo Orientador Context (fonte versionada).

Renderiza para orientador-context/docs/architecture/orientador-context.png.
Rode a partir da raiz do repo:
    python3 orientador-context/docs/architecture/orientador-context.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.security import Cognito
from diagrams.aws.compute import Lambda, Fargate
from diagrams.aws.database import Aurora
from diagrams.aws.storage import S3
from diagrams.aws.analytics import Athena, GlueCrawlers, GlueDataCatalog
from diagrams.aws.integration import Eventbridge
from diagrams.aws.ml import Bedrock
from diagrams.onprem.client import Users

OUT = "orientador-context/docs/architecture/orientador-context"

with Diagram("Orientador Context — arquitetura e fluxo de dados",
             filename=OUT, show=False, outformat="png", direction="LR"):

    prof = Users("Professor/Aluno\n(portal)")

    with Cluster("Portal 'A Arte do Possivel'"):
        cf = CloudFront("CloudFront\n/orientador-context/*")
        api = APIGateway("HTTP API")
        cog = Cognito("Cognito (JWT)\nRBAC por grupo")

    with Cluster("Modulo Orientador Context"):
        agent = Lambda("Agente (Lambda)\nBedrock Converse + tools")
        bedrock = Bedrock("Bedrock\n(Nova/Claude)")

    with Cluster("Data lake (GA)"):
        athena = Athena("Athena\nwg moodle-datalake")
        catalog = GlueDataCatalog("Glue Catalog\nmoodle_datalake")
        crawler = GlueCrawlers("Glue Crawler")
        lake = S3("S3 (CSV curado)\nalunos/cursos/notas/...")

    with Cluster("Backbone Moodle (projeto apartado)"):
        moodle = Fargate("Moodle\n(ECS Fargate)")
        aurora = Aurora("Aurora PostgreSQL\n(privado)")
        exporter = Lambda("Export (Lambda)\nRDS Data API")
        sched = Eventbridge("EventBridge\n(diario)")

    # --- Fluxo de PERGUNTA (chat), da direita p/ esquerda no consumo ---
    prof >> Edge(label="1. pergunta (HTTPS)") >> cf >> Edge(label="JWT") >> api
    api >> Edge(label="valida token") >> cog
    api >> Edge(label="2. invoca") >> agent
    agent >> Edge(label="3. tool-use") >> bedrock
    agent >> Edge(label="4. SQL") >> athena
    athena >> Edge(label="metadados") >> catalog
    athena >> Edge(label="le dados / grava resultados") >> lake

    # --- Fluxo de INGESTAO (Moodle -> data lake) ---
    moodle >> Edge(label="grava") >> aurora
    sched >> Edge(label="agenda") >> exporter
    aurora >> Edge(label="A. SELECT (Data API)") >> exporter
    exporter >> Edge(label="B. escreve CSV") >> lake
    exporter >> Edge(label="C. dispara") >> crawler
    crawler >> Edge(label="D. cataloga") >> catalog
