"""Diagrama do módulo Avaliações (correção de provas).

Borda + auth, API HTTP + fila assíncrona, agentes Strands no AgentCore Runtime, OMR
determinístico (OpenCV), Provas Online (RAG/KB), Evaluation e observabilidade.
Render (da raiz): python3 docs/architecture/avaliacao.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.security import Cognito, SecretsManager
from diagrams.aws.compute import Lambda, LambdaFunction
from diagrams.aws.integration import SQS
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock
from diagrams.aws.management import Cloudwatch, SystemsManagerParameterStore
from diagrams.onprem.client import Users

with Diagram("Módulo Avaliações", filename="docs/architecture/avaliacao",
             show=False, outformat="png", direction="LR",
             graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Professor / Admin")

    with Cluster("Borda + Auth"):
        cf = CloudFront("CloudFront")
        cognito = Cognito("Cognito")

    with Cluster("Frontend (S3/OAC)"):
        fe = S3("index.html + app.js\n(+ opencv.js: OMR/QR no navegador)")

    with Cluster("API (HTTP + JWT + header secreto)"):
        api = APIGateway("HTTP API /api/*")
        api_fn = Lambda("API Lambda\nsubmissões, rubricas, provas,\ntemplates, model-config,\nevaluations, analytics, online-exams")
        secret = SecretsManager("Header de origem")

    with Cluster("Assíncrono"):
        queue = SQS("SQS + DLQ")
        worker = Lambda("Worker\n(conc. reservada, idempotente)")
        omr = LambdaFunction("OpenCV layer\nOMR cartão + QR (ID_Exam)")

    with Cluster("Agentes (AgentCore Runtime)"):
        runtime = Bedrock("Agentes Strands\ntranscrição/redação/prova/autor/\nanswersheet/judge/examgen")
        models = Bedrock("Bedrock Converse\n(modelos parametrizados)")

    with Cluster("Conhecimento (Provas Online)"):
        kb = Bedrock("Bedrock Knowledge Base\n(RAG — S3 Vectors + Titan v2)")

    with Cluster("Dados"):
        ddb = Dynamodb("DynamoDB\nsubmissions/corrections/rubrics/\nexams/model_config/online-*")
        uploads = S3("Uploads + referências")

    with Cluster("Observabilidade / Config"):
        cw = Cloudwatch("CloudWatch EMF\ntokens/custo/latência")
        ssm = SystemsManagerParameterStore("SSM\nagent-runtime-arn")

    users >> Edge(label="HTTPS") >> cf
    cf >> Edge(label="/") >> fe
    cf >> Edge(label="/api/* + header") >> api >> api_fn
    secret >> Edge(style="dotted") >> api_fn
    users >> Edge(label="PKCE", style="dashed") >> cognito

    api_fn >> ddb
    api_fn >> Edge(label="presigned") >> uploads
    api_fn >> Edge(label="202") >> queue >> worker
    api_fn >> Edge(label="Retrieve (RAG)", style="dashed") >> kb
    api_fn >> Edge(label="judge/examgen (InvokeAgentRuntime)", style="dashed") >> runtime
    worker >> Edge(label="InvokeAgentRuntime (IAM)") >> runtime
    worker >> omr
    omr >> Edge(style="dotted", label="imagem + referência") >> uploads
    runtime >> models
    worker >> ddb
    worker >> Edge(style="dotted") >> cw
    worker >> Edge(style="dotted") >> ssm
