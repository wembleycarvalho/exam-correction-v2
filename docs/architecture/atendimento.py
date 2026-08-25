"""Diagrama do módulo Atendimento (Amazon Connect).

Sem infra própria: o portal abre o workspace do Amazon Connect em janela dedicada.
Render (da raiz): python3 docs/architecture/atendimento.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront
from diagrams.aws.engagement import Connect
from diagrams.onprem.client import Users

with Diagram("Módulo Atendimento (Amazon Connect)", filename="docs/architecture/atendimento",
             show=False, outformat="png", direction="LR",
             graph_attr={"fontsize": "18", "pad": "0.4", "splines": "spline"}):
    users = Users("Atendente")

    with Cluster("Portal"):
        cf = CloudFront("CloudFront\n(capítulo Atendimento)")

    connect = Connect("Amazon Connect\nvoz / chat / WhatsApp / tasks\n(agent workspace)")

    users >> Edge(label="portal") >> cf
    cf >> Edge(label="window.open (CSP bloqueia iframe)", style="dashed") >> connect
    users >> Edge(label="login Connect + microfone") >> connect
