# Deploy do Orientador Context (interino, cirúrgico)

Ferramenta **reproduzível** do deploy que coloca o módulo no ar **sem redeployar o portal**.
Existe porque o `cdk deploy` do portal inteiro exige **Docker** (imagem do Entrevistador) e não
roda bem a partir do repositório no OneDrive. É o caminho **interino**; a forma canônica
(CDK-gerenciada) é `infra/modules/orientador_context.py` + `-c modules=...,orientador-context`.

## O que faz (`./deploy.sh`)
1. Deploya a **stack CDK standalone** `orientador-context` (Lambda agente + HTTP API +
   authorizer Cognito importado do portal + IAM least-privilege). Sem VPC, sem Docker.
2. Liga a rota **`/orientador-context/*`** na distribution CloudFront do portal, de forma
   **aditiva e idempotente** (clona a config do behavior `/lms/*`, preserva os demais).
3. Publica `frontend/app.js` (menu + telas) e invalida o cache.

Resolve sozinho os IDs (User Pool, Client, Distribution, bucket do frontend) do stack
`exam-correction-v2` e o `DataLakeBucket` do stack `moodle-backbone`.

## Reconciliar para o CDK do portal (quando houver Docker)
```bash
./teardown.sh    # remove o behavior + a stack standalone (módulo sai do ar)
# depois, no repo raiz (com Docker):
MODULES="correcao,entrevistador,orientador,lms,orientador-context" ./scripts/deploy.sh
```

> `layer/`, `.venv/`, `cdk.out/`, `out.json` são gerados no deploy (gitignored).
