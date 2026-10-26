"""Diagrama do módulo LMS de Vídeo (busca multimodal + resumo).

Ingestão (Marengo → S3 Vectors) e busca (query embedding → QueryVectors) + Pegasus.
Render (da raiz): python3 docs/architecture/lms.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.security import Cognito
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock
from diagrams.onprem.client import Users

with Diagram("Módulo LMS de Vídeo", filename="docs/architecture/lms",
             show=False, outformat="png", direction="LR",
             graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Professor / Admin")

    with Cluster("Borda + Auth"):
        cf = CloudFront("CloudFront")
        cognito = Cognito("Cognito")

    media = S3("S3 acervo (mp4)\n/lms/media/* (OAC)")

    with Cluster("Ingestão (offline, 1x por vídeo)"):
        ingest = Lambda("IngestFn")
        marengo_i = Bedrock("Marengo Embed 3.0\nStartAsyncInvoke\n(visual+audio+transcription)")
        s3out = S3("S3 saída embeddings")

    with Cluster("Busca (online)"):
        api = APIGateway("HTTP API /lms/*")
        apifn = Lambda("ApiFn (router)\nsearch/similar/summary/eval")
        marengo_q = Bedrock("Marengo\n(embed da query)")
        pegasus = Bedrock("Pegasus 1.2\n(vídeo → texto)")

    with Cluster("Vetores + Catálogo"):
        vectors = S3("S3 Vectors\nlms-segments (512d, cosseno)")
        ddb = Dynamodb("DynamoDB\nCatalog / Ingest")

    users >> Edge(label="HTTPS") >> cf
    users >> Edge(label="PKCE", style="dashed") >> cognito
    cf >> Edge(label="/lms/media/*") >> media
    cf >> Edge(label="/lms/* (JWT)") >> api >> apifn

    ingest >> Edge(label="StartAsyncInvoke") >> marengo_i >> Edge(label="embeddings.json") >> s3out
    ingest >> Edge(label="lê saída") >> s3out
    ingest >> Edge(label="PutVectors") >> vectors
    ingest >> ddb

    apifn >> Edge(label="InvokeModel / async") >> marengo_q
    apifn >> Edge(label="Query/Get/ListVectors") >> vectors
    apifn >> Edge(label="resumo/Q&A", style="dashed") >> pegasus
    apifn >> ddb
