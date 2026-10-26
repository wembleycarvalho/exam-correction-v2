"""Diagrama de arquitetura — Exam Correction v2 (diagrama como código).

Cobre: borda segura (CloudFront/WAF), auth (Cognito), API HTTP + fila assíncrona,
agentes Strands no AgentCore Runtime, correção (redação/prova) e leitura de cartão-resposta
(OMR determinístico com OpenCV — no navegador e no servidor), templates, QR/ID_Exam,
Evaluation (model-as-judge) e observabilidade.

Render (da raiz do repo): python3 docs/architecture/exam-correction-v2.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.security import Cognito, WAF, SecretsManager
from diagrams.aws.compute import Lambda, LambdaFunction
from diagrams.aws.integration import SQS
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock
from diagrams.aws.management import Cloudwatch, SystemsManagerParameterStore
from diagrams.onprem.client import Users

with Diagram("Exam Correction v2", filename="docs/architecture/exam-correction-v2",
             show=False, outformat="png", direction="LR",
             graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Usuário\n(professor/admin)")

    with Cluster("Borda (único ponto de entrada)"):
        waf = WAF("WAF")
        cf = CloudFront("CloudFront")

    with Cluster("Auth"):
        cognito = Cognito("Cognito\n(sem self-signup)")

    with Cluster("Frontend (S3/OAC)"):
        fe = S3("index.html + app.js\n+ styles.css")
        opencvjs = S3("opencv.js\n(OMR + QR no navegador)")

    with Cluster("API (HTTP + JWT + header secreto)"):
        api = APIGateway("HTTP API /api/*")
        api_fn = Lambda("API Lambda\nsubmissões, rubricas, provas,\ntemplates, model-config,\nevaluations, analytics")
        secret = SecretsManager("Header de origem")

    with Cluster("Assíncrono"):
        queue = SQS("SQS + DLQ")
        worker = Lambda("Worker\n(conc. reservada)")
        omr = LambdaFunction("OpenCV layer\nOMR cartão + QR (ID_Exam)")

    with Cluster("Agentes (AgentCore Runtime)"):
        runtime = Bedrock("Agentes Strands\ntranscrição/redação/prova/\nautor/answersheet/judge")
        models = Bedrock("Bedrock Converse\n(modelos parametrizados)")

    with Cluster("Dados"):
        ddb = Dynamodb("DynamoDB\nsubmissions/corrections/rubrics/\nexams/model_config(+templates)/\ntest_registry")
        uploads = S3("Uploads + referências\nde template")

    with Cluster("Observabilidade / Config"):
        cw = Cloudwatch("CloudWatch EMF\ntokens/custo/latência")
        ssm = SystemsManagerParameterStore("SSM\nagent-runtime-arn")

    users >> Edge(label="HTTPS") >> cf
    waf >> Edge(style="dotted") >> cf
    cf >> Edge(label="/") >> fe
    fe >> Edge(style="dashed", label="Ler cartão") >> opencvjs
    cf >> Edge(label="/api/* + header") >> api >> api_fn
    secret >> Edge(style="dotted") >> api_fn
    users >> Edge(label="PKCE", style="dashed") >> cognito

    api_fn >> ddb
    api_fn >> Edge(label="presigned") >> uploads
    api_fn >> Edge(label="202") >> queue >> worker
    api_fn >> Edge(label="judge (InvokeAgentRuntime)", style="dashed") >> runtime
    worker >> Edge(label="InvokeAgentRuntime (IAM)") >> runtime
    worker >> omr
    omr >> Edge(style="dotted", label="imagem + referência") >> uploads
    runtime >> models
    worker >> ddb
    worker >> Edge(style="dotted") >> cw
    worker >> Edge(style="dotted") >> ssm
