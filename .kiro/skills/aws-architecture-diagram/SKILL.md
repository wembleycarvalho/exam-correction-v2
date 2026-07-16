---
name: aws-architecture-diagram
description: >
  Gera diagramas de arquitetura AWS como código usando a biblioteca Python `diagrams`
  (DSL do mingrammer) renderizada via Graphviz. Substitui o AWS Diagram MCP server
  (deprecado e com histórico de RCE). Use quando precisar criar/atualizar um diagrama de
  arquitetura em PNG a partir de uma descrição textual ou do código/infra do projeto.
---

# Skill: Diagrama de Arquitetura AWS (diagrams + Graphviz)

## Quando usar
- Criar ou atualizar o diagrama de arquitetura da solução (ex.: `docs/architecture/`).
- Traduzir a arquitetura descrita no spec/design ou nos templates SAM em um PNG.

## Por que esta abordagem
- O `awslabs.aws-diagram-mcp-server` foi **deprecado** e teve uma vulnerabilidade de RCE
  (executava código Python arbitrário). A recomendação atual da AWS é usar o "diagram
  agent skill": gerar o diagrama escrevendo código `diagrams` e renderizando localmente,
  sem servidor MCP. Aqui o agente escreve e roda um `.py` versionado no workspace — mesmo
  modelo de confiança de qualquer código do repo, sem endpoint de exec exposto.

## Pré-requisitos (já presentes neste ambiente)
- Graphviz (`dot`) instalado. Verifique: `dot -V`. Instale com `brew install graphviz`.
- Lib Python: `pip3 install diagrams`.

## Convenções do projeto
- Diagrama = **código versionado**: salve o fonte em `docs/architecture/<nome>.py`.
- Renderize para PNG no mesmo diretório: `Diagram(filename="docs/architecture/<nome>", show=False, outformat="png")`.
- Use `show=False` (não abrir viewer). Rode a partir da raiz do repo.
- Agrupe por domínio com `Cluster` (Edge, Auth, API, Assíncrono, Agentes, Dados, Observabilidade).
- Rótulos em PT-BR curtos.

## Como escrever (padrão)
```python
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.security import Cognito, WAF, SecretsManager
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SQS
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock            # usar p/ Bedrock e AgentCore (sem ícone próprio)
from diagrams.aws.management import Cloudwatch, SystemsManagerParameterStore
from diagrams.onprem.client import Users

with Diagram("Titulo", filename="docs/architecture/nome", show=False, outformat="png", direction="LR"):
    users = Users("Usuário")
    with Cluster("Edge"):
        cf = CloudFront("CloudFront + WAF")
    ...
    users >> cf
```

## Mapa de nós AWS úteis (import path)
- `diagrams.aws.network`: `CloudFront`, `APIGateway`, `VPC`, `Route53`
- `diagrams.aws.security`: `Cognito`, `WAF`, `SecretsManager`, `IAM`, `IAMRole`
- `diagrams.aws.compute`: `Lambda`
- `diagrams.aws.integration`: `SQS`, `SNS`, `Eventbridge`
- `diagrams.aws.database`: `Dynamodb`
- `diagrams.aws.storage`: `S3`
- `diagrams.aws.ml`: `Bedrock` (use para modelos e para AgentCore Gateway/Runtime)
- `diagrams.aws.management`: `Cloudwatch`, `SystemsManagerParameterStore`
- `diagrams.aws.analytics`: `ElasticsearchService` (proxy p/ OpenSearch Serverless)
- `diagrams.onprem.client`: `Users`

## Renderizar
```bash
python3 docs/architecture/<nome>.py && ls docs/architecture/<nome>.png
```

## Dicas
- Se um serviço novo não tiver ícone (ex.: AgentCore), use o nó mais próximo (`Bedrock`)
  com rótulo explícito.
- Prefira poucos clusters e conexões claras; um diagrama legível vale mais que exaustivo.
- Atualize o `.py` quando a arquitetura mudar e re-renderize (diagrama sempre em dia).
