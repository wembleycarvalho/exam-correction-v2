"""Diagrama de arquitetura do modulo Gateway Inference (EKS Fargate + streaming SSE).

Fonte versionado (skill aws-architecture-diagram). Render:
  python3 agentcore-gateway-inference/eks/docs/architecture/gateway-inference-eks.py
Gera gateway-inference-eks.png no mesmo diretorio.
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, ElbApplicationLoadBalancer
from diagrams.aws.security import Cognito, SecretsManager, IAMRole
from diagrams.aws.compute import Fargate
from diagrams.aws.ml import Bedrock
from diagrams.aws.management import Cloudwatch, SystemsManagerParameterStore
from diagrams.onprem.client import Users

_GRAPH = {"fontsize": "11", "pad": "0.5", "nodesep": "0.6", "ranksep": "1.1",
          "splines": "spline"}

with Diagram("Gateway Inference — EKS Fargate (streaming SSE + Guardrail + memoria)",
             filename="agentcore-gateway-inference/eks/docs/architecture/gateway-inference-eks",
             show=False, outformat="png", direction="LR", graph_attr=_GRAPH):

    user = Users("Professor/Coordenador\n(portal, JWT Cognito)")

    with Cluster("Borda"):
        cf = CloudFront("CloudFront\n/agentcore/* (sem cache)")
        alb = ElbApplicationLoadBalancer("ALB internet-facing\n(AWS LB Controller)")

    with Cluster("EKS Fargate — cluster strands-obs-demo (ns gwinf)"):
        pod = Fargate("pod gwinf-agent\nFastAPI + Strands\nopentelemetry-instrument")
        irsa = IAMRole("IRSA\n(privilegio minimo)")

    with Cluster("Bedrock"):
        guardrail = Bedrock("Guardrail nativo\nApplyGuardrail\n(entrada + saida)")
        gateway = Bedrock("AgentCore Gateway\nbedrock-mantle\n(54 modelos)")

    with Cluster("Auth / Config / Segredos"):
        cognito = Cognito("Cognito (portal)")
        ssm = SystemsManagerParameterStore("SSM /gateway-inference/*")
        secret = SecretsManager("Secrets Manager")

    obs = Cloudwatch("CloudWatch GenAI\nObservability / X-Ray")

    # --- fluxo principal da requisicao (numerado) ---
    user >> Edge(label="1. /ask/stream (SSE) + history") >> cf
    cf >> Edge(label="2. http-only, sem buffer") >> alb
    alb >> Edge(label="3. request") >> pod
    pod >> Edge(label="4. Guardrail entrada") >> guardrail
    pod >> Edge(label="5. inferencia (token m2m)") >> gateway
    pod >> Edge(label="6. Guardrail saida") >> guardrail
    pod >> Edge(label="7. resposta final\n(FE aguarda p/ guardrail)", color="darkgreen") >> alb

    # --- config/auth/segredos (dependencias, tracejado) ---
    pod >> Edge(style="dashed", color="gray", label="valida JWT") >> cognito
    pod >> Edge(style="dashed", color="gray", label="config + guardrail-id") >> ssm
    pod >> Edge(style="dashed", color="gray", label="token m2m") >> secret

    # --- observabilidade nativa (pontilhado) ---
    pod >> Edge(style="dotted", color="blue", label="spans gen_ai.* (ADOT, sem /health)") >> obs

    irsa - Edge(style="invis") - pod
