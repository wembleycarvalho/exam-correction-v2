"""Diagrama do módulo Orientador Acadêmico (knowledge graph + agente).

Bridge Lambda → AgentCore Runtime (Strands, container ARM64 na VPC) → Neptune.
Render (da raiz): python3 docs/architecture/orientador.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront
from diagrams.aws.security import Cognito
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Neptune
from diagrams.aws.ml import Bedrock
from diagrams.aws.management import SystemsManagerParameterStore
from diagrams.onprem.client import Users

with Diagram("Módulo Orientador Acadêmico", filename="docs/architecture/orientador",
             show=False, outformat="png", direction="LR",
             graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Professor / Coordenador")

    with Cluster("Borda + Auth"):
        cf = CloudFront("CloudFront\n/orientador/api")
        cognito = Cognito("Cognito")

    bridge = Lambda("bridge Lambda\n(ask aluno/coordenador → InvokeAgentRuntime)")

    with Cluster("AgentCore Runtime (VPC, subnets privadas c/ NAT)"):
        agent = Bedrock("Agente Strands\n(TOOLS aluno + COORD_TOOLS)")
        models = Bedrock("Bedrock Nova Pro\n(Converse)")

    with Cluster("Grafo (fonte da verdade)"):
        neptune = Neptune("Neptune\nnós: Program/Discipline/Competency/\nCareer/Student · arestas incl. ENROLLED")

    ssm = SystemsManagerParameterStore("SSM\nagent-runtime-arn")

    users >> Edge(label="HTTPS") >> cf
    users >> Edge(label="PKCE", style="dashed") >> cognito
    cf >> bridge
    ssm >> Edge(style="dotted", label="ARN") >> bridge
    bridge >> Edge(label="InvokeAgentRuntime (IAM)") >> agent
    agent >> Edge(label="Converse") >> models
    agent >> Edge(label="hidrata no cold start /\naction=load") >> neptune
