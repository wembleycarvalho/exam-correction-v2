"""Diagrama de arquitetura do módulo AgentCore — Gateway Inference (fonte versionada).

Renderiza para docs/architecture/agentcore-gateway-inference.png.
Rode a partir da raiz do repo:
    python3 agentcore-gateway-inference/docs/architecture/agentcore-gateway-inference.py

Nota: AgentCore não tem ícone próprio na lib `diagrams`; usamos o ícone do Bedrock com
rótulos explícitos (convenção do skill de diagramas do projeto).
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.security import Cognito, SecretsManager
from diagrams.aws.compute import Lambda
from diagrams.aws.ml import Bedrock
from diagrams.aws.management import Cloudwatch, SystemsManagerParameterStore
from diagrams.onprem.client import Users

OUT = "agentcore-gateway-inference/docs/architecture/agentcore-gateway-inference"

with Diagram("AgentCore — Gateway Inference (portal)",
             filename=OUT, show=False, outformat="png", direction="LR"):

    user = Users("Professor/Aluno\n(portal)")

    with Cluster("Portal 'A Arte do Possivel'"):
        cf = CloudFront("CloudFront\n/agentcore/*")
        api = APIGateway("HTTP API")
        cog = Cognito("Cognito (JWT)\n(pool do portal)")

    with Cluster("Modulo AgentCore Gateway Inference"):
        router = Lambda("Router (Lambda)\nask | models | mantle/metrics")
        ssm = SystemsManagerParameterStore("SSM\n/gateway-inference/*")

    with Cluster("Amazon Bedrock AgentCore"):
        runtime = Bedrock("AgentCore Runtime\nagente Strands (CodeZip)")
        gateway = Bedrock("AgentCore Gateway\ntarget bedrock-mantle")

    secret = SecretsManager("Secrets Manager\ntoken m2m (OAuth)")
    llms = Bedrock("bedrock-mantle\n54 modelos (Claude/DeepSeek/GPT-5/...)")
    cw = Cloudwatch("CloudWatch\nGenAI Observability + AWS/BedrockMantle")

    # ---- Chat / Evaluation ----
    user >> Edge(label="1. HTTPS") >> cf >> Edge(label="JWT") >> api
    api >> Edge(label="valida token") >> cog
    api >> Edge(label="2. invoca") >> router
    router >> Edge(label="3. le config/ARN") >> ssm
    router >> Edge(label="4. InvokeAgentRuntime\n(nao-streaming)") >> runtime
    runtime >> Edge(label="token m2m") >> secret
    runtime >> Edge(label="5. OpenAI/Anthropic/Responses") >> gateway >> Edge(label="6. LLM") >> llms
    runtime >> Edge(label="traces/tokens (ADOT)") >> cw

    # ---- Observability admin (Mantle-config) ----
    router >> Edge(style="dashed", label="mantle/metrics") >> cw
    # ---- models ----
    router >> Edge(style="dotted", label="models (token m2m)") >> gateway
