"""Diagrama do módulo Entrevistador Virtual (voz em tempo real).

Exceção ao serverless: ECS Fargate (ARM64) atrás de ALB, servido pelo CloudFront.
Render (da raiz): python3 docs/architecture/interviewer.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, ElbApplicationLoadBalancer
from diagrams.aws.security import Cognito
from diagrams.aws.compute import Fargate
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock
from diagrams.onprem.client import Users

with Diagram("Módulo Entrevistador Virtual", filename="docs/architecture/interviewer",
             show=False, outformat="png", direction="LR",
             graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Candidato / RH")

    with Cluster("Borda + Auth"):
        cf = CloudFront("CloudFront\n/entrevistador/*")
        cognito = Cognito("Cognito")

    with Cluster("VPC default (sem NAT — subnet pública + IGW)"):
        alb = ElbApplicationLoadBalancer("ALB\n(só aceita header de origem)")
        task = Fargate("ECS Fargate ARM64\nFastAPI + WebSocket (uvicorn:8080)")

    with Cluster("Bedrock"):
        sonic = Bedrock("Nova Sonic\n(voz tempo real, WS bidirecional)")
        lite = Bedrock("Nova Lite\n(relatório de RH)")
        stability = Bedrock("Stability (us-west-2)\n(avatar)")

    with Cluster("Estado"):
        ddb = Dynamodb("DynamoDB\nVagas / Reports / Avatars (RETAIN)")
        avatars = S3("S3 avatares (privado)")

    users >> Edge(label="WSS / HTTPS") >> cf
    users >> Edge(label="PKCE", style="dashed") >> cognito
    cf >> Edge(label="header de origem") >> alb >> task
    task >> Edge(label="WS bidirecional") >> sonic
    task >> Edge(style="dashed") >> lite
    task >> Edge(style="dashed") >> stability
    task >> ddb
    task >> avatars
