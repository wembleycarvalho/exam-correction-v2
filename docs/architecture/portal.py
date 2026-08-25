"""Diagrama macro do portal — A Arte do Possível (Exam Correction v2).

Ponto de entrada único (CloudFront) → 5 módulos. Render (da raiz):
    python3 docs/architecture/portal.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway, ElbApplicationLoadBalancer
from diagrams.aws.security import Cognito
from diagrams.aws.compute import Lambda, Fargate
from diagrams.aws.database import Dynamodb, Neptune
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock
from diagrams.aws.engagement import Connect
from diagrams.onprem.client import Users

with Diagram("A Arte do Possível — Portal (5 módulos)",
             filename="docs/architecture/portal", show=False, outformat="png",
             direction="LR", graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Professor / Admin")

    with Cluster("Borda + Auth"):
        cf = CloudFront("CloudFront\n(entrada única)")
        cognito = Cognito("Cognito\n(sem self-signup)")

    fe = S3("Frontend SPA\n(S3/OAC)")

    with Cluster("Avaliações  (/api/*)"):
        aval = Lambda("API + Worker\n+ AgentCore + KB + OMR")

    with Cluster("LMS de Vídeo  (/lms/*)"):
        lms = Lambda("API/Ingest")
        lms_vec = S3("S3 Vectors\n+ Marengo/Pegasus")

    with Cluster("Orientador  (/orientador/*)"):
        ori = Lambda("bridge")
        ori_rt = Bedrock("AgentCore Runtime\n(Strands)")
        ori_db = Neptune("Neptune")

    with Cluster("Entrevistador  (/entrevistador/*)"):
        alb = ElbApplicationLoadBalancer("ALB")
        ent = Fargate("Fargate\nNova Sonic (voz)")

    connect = Connect("Atendimento\n(Amazon Connect)")

    users >> Edge(label="HTTPS") >> cf
    users >> Edge(label="PKCE", style="dashed") >> cognito
    cf >> Edge(label="/") >> fe
    cf >> Edge(label="/api/*") >> aval
    cf >> Edge(label="/lms/*") >> lms >> lms_vec
    cf >> Edge(label="/orientador/*") >> ori >> ori_rt >> ori_db
    cf >> Edge(label="/entrevistador/*") >> alb >> ent
    users >> Edge(label="janela", style="dashed") >> connect
