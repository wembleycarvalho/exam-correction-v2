# VideoPlatform

Plataforma de vídeo sob demanda (VOD) na AWS: upload de vídeos, pipeline de
processamento (transcode ABR + legenda automática), entrega segura e um
frontend web com upload, biblioteca/revisão, player e analytics.

> Protótipo. Conta AWS única, região `us-east-1`. Todos os usuários são admin.
> Entrega segura **sem DRM** nesta fase (ver `docs/03-drm.md` para o caminho de DRM).

## Visão geral

```
Upload (Web) ──> S3 raw-videos/{videoId}/source.mp4
                      │  (evento S3)
                      ▼
            Step Functions (orquestração)
                      ├─ AWS Elemental MediaConvert  → HLS ABR 1080/720/480/360
                      ├─ Amazon Transcribe (pt-BR)   → legenda WebVTT
                      └─ Lambda                      → DynamoDB status = "revisar" + custo
                      ▼
       S3 video-profiles/{videoId}/hls/… + /legenda/…
                      │  (bucket PRIVADO)
                      ▼
   CloudFront (OAC + cookies assinados + WAF + HTTPS)
                      ▼
            Player Shaka (Web) — só após login (Cognito)
```

## Estrutura do repositório

| Pasta       | Conteúdo                                                              |
|-------------|----------------------------------------------------------------------|
| `docs/`     | Arquitetura, segurança, DRM, watermarking forense e custos           |
| `infra/`    | Infraestrutura como código (AWS CDK, TypeScript)                     |
| `backend/`  | Funções Lambda (API + pipeline) em TypeScript                        |
| `frontend/` | SPA React (Vite) com os 4 menus                                      |

## Status do vídeo (DynamoDB)

```
enviando ──> processando ──> revisar ──> pronto
                   └──────────> erro
```

- **enviando**: upload em andamento (o objeto ainda não existe no S3). Se o
  upload for abandonado, o registro permanece aqui (o multipart incompleto é
  abortado pela regra de ciclo de vida do bucket em 2 dias).
- **processando**: upload concluído, pipeline rodando.
- **revisar**: profiles e legenda gerados; usuário informa título, descrição,
  ajusta sincronismo da legenda e pode gerar traduções (es/en).
- **pronto**: publicado pelo usuário após revisão (único estado que toca o Play).
- **erro**: falha na pipeline (motivo registrado).

## Menus do frontend

1. **Upload** — envio de vídeo (multipart, sem limite de tamanho) com status de upload e de processamento.
2. **Biblioteca / Revisão** — lista de vídeos, edição de metadados, ajuste de legenda, tradução e transição `revisar → pronto`.
3. **Player** — informa o `videoId`; o backend autoriza e emite cookies assinados; o Shaka toca via CloudFront.
4. **Analytics** — contagem de plays por vídeo (registrada no momento do play) e custo estimado de processamento.

## Pré-requisitos

- Node.js 20+
- AWS CDK v2 (`npm i -g aws-cdk`)
- Credenciais AWS válidas no `.env` (temporárias/Isengard — expiram; renove quando necessário)

## Como rodar (resumo — detalhes em `infra/README.md`)

```bash
# 1. Carregar credenciais (temporárias) no shell
source .env

# 2. Infra
cd infra && npm install
npx cdk bootstrap aws://<ACCOUNT_ID>/us-east-1   # primeira vez na conta/região
npx cdk deploy --require-approval never
cd ..

# 3. Publicar o frontend (lê os outputs, builda, injeta config e faz sync no bucket)
bash scripts/deploy-frontend.sh

# 4. Criar um usuário de login (self sign-up está desabilitado por segurança)
bash scripts/create-user.sh voce@exemplo.com 'SenhaForte123'

# 5. Abrir a aplicação na URL do CloudFront (output CloudFrontUrl)
```

Para desenvolvimento local do frontend (`cd frontend && npm run dev`), configure
`frontend/.env` a partir de `.env.example` com o `ApiUrl` e os IDs do Cognito.
A reprodução com cookies assinados exige same-origin, então teste o Player pela
URL do CloudFront.

## Segurança

- `.env` está no `.gitignore` — **nunca** commitar credenciais.
- Buckets S3 totalmente privados; acesso só via CloudFront com Origin Access Control (OAC).
- Conteúdo entregue com **cookies assinados** do CloudFront, com TTL curto, emitidos só após login.
- Detalhes e limitações (e por que sem DRM ainda é seguro) em `docs/02-seguranca.md`.
