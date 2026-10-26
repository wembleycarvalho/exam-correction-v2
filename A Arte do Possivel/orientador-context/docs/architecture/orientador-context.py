"""Diagrama de arquitetura do módulo Orientador Context (fonte versionada).

Reflete a arquitetura AGÊNTICA: o chat é atendido por um agente Strands no Amazon
Bedrock AgentCore Runtime (memória gerenciada + web search via AgentCore Gateway),
enquanto as telas determinísticas continuam consultando o data lake (Athena) direto.

Renderiza para orientador-context/docs/architecture/orientador-context.png.
Rode a partir da raiz do repo:
    python3 orientador-context/docs/architecture/orientador-context.py

Nota: AgentCore não tem ícone próprio na lib `diagrams`; usamos o ícone do Bedrock
com rótulos explícitos (convenção do skill de diagramas do projeto).
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
from diagrams.aws.management import SystemsManagerParameterStore
from diagrams.onprem.network import Internet
from diagrams.onprem.client import Users

OUT = "orientador-context/docs/architecture/orientador-context"

with Diagram("Orientador Context — arquitetura agentica (AgentCore) e fluxo de dados",
             filename=OUT, show=False, outformat="png", direction="LR"):

    prof = Users("Professor/Aluno\n(portal)")

    with Cluster("Portal 'A Arte do Possivel'"):
        cf = CloudFront("CloudFront\n/orientador-context/*")
        api = APIGateway("HTTP API")
        cog = Cognito("Cognito (JWT)\nRBAC por grupo")

    with Cluster("Modulo Orientador Context"):
        bridge = Lambda("Router (Lambda)\nchat -> Runtime | telas -> Athena")
        ssm = SystemsManagerParameterStore("SSM Params\nruntime-arn / gateway-url")

    with Cluster("Amazon Bedrock AgentCore"):
        runtime = Bedrock("AgentCore Runtime\nagente Strands (CodeZip)")
        memory = Bedrock("AgentCore Memory\n(curto prazo, 30d)")
        model = Bedrock("Bedrock Converse\n(Nova/Claude)")
        gateway = Bedrock("AgentCore Gateway\nweb-search (MCP/SigV4)")

    web = Internet("Web\n(noticias/fatos atuais)")

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

    # --- Fluxo de PERGUNTA (chat agentico) ---
    prof >> Edge(label="1. pergunta (HTTPS)") >> cf >> Edge(label="JWT") >> api
    api >> Edge(label="valida token") >> cog
    api >> Edge(label="2. invoca") >> bridge
    bridge >> Edge(label="3. le ARN") >> ssm
    bridge >> Edge(label="4. InvokeAgentRuntime\n(nao-streaming)") >> runtime
    runtime >> Edge(label="5. Converse + tool-use") >> model
    runtime >> Edge(label="memoria da sessao") >> memory
    runtime >> Edge(label="6. SQL (dados Moodle)") >> athena
    runtime >> Edge(label="7. web search (MCP)") >> gateway >> Edge(label="indice AWS") >> web

    # --- Telas determinísticas (sem agente): Lambda -> Athena direto ---
    bridge >> Edge(style="dashed", label="telas (perfil/grafo/coordenacao)") >> athena
    athena >> Edge(label="metadados") >> catalog
    athena >> Edge(label="le dados / grava resultados") >> lake

    # --- Fluxo de INGESTAO (Moodle -> data lake) ---
    moodle >> Edge(label="grava") >> aurora
    sched >> Edge(label="agenda") >> exporter
    aurora >> Edge(label="A. SELECT (Data API)") >> exporter
    exporter >> Edge(label="B. escreve CSV") >> lake
    exporter >> Edge(label="C. dispara") >> crawler
    crawler >> Edge(label="D. cataloga") >> catalog
