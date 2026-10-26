# Infra (AWS CDK) — VideoPlatform

Stack única `videoplatform-stack` em `us-east-1`. Compõe os constructs:
Storage (S3 + DynamoDB), Auth (Cognito), Delivery (CloudFront + cookies
assinados + WAF), Pipeline (Step Functions + MediaConvert + Transcribe) e Api
(API Gateway + Lambda).

## Pré-requisitos

- Node.js 20+
- Credenciais AWS no shell. No protótipo elas vêm do `.env` (temporárias):
  ```bash
  source ../.env     # exporta AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN
  ```
  > Credenciais Isengard expiram. Se o deploy falhar com erro de token,
  > renove-as e rode `source ../.env` de novo.

## Deploy

```bash
cd infra
npm install

# 1. Bootstrap (uma vez por conta/região)
npx cdk bootstrap aws://<ACCOUNT_ID>/us-east-1

# 2. Deploy
npx cdk deploy --require-approval never
```

Ao final, os **Outputs** incluem: `UserPoolId`, `UserPoolClientId`,
`CloudFrontDomain`, `CloudFrontUrl`, `FrontendBucketName`, `MediaBucketName`,
`ApiUrl`.

## Publicar o frontend

```bash
# da raiz do repo, com credenciais no shell:
bash scripts/deploy-frontend.sh
```
O script lê os outputs, builda a SPA, injeta `config.js` (same-origin) e
sincroniza com o bucket do frontend, invalidando o CloudFront.

## Criar um usuário (login)

O self sign-up está desabilitado por segurança. Crie um usuário admin:

```bash
bash scripts/create-user.sh voce@exemplo.com 'SenhaForte123'
```

## Testar o fluxo

1. Abra `CloudFrontUrl` e faça login.
2. **Upload**: envie um `.mp4`. Acompanhe o status até `revisar`.
3. **Biblioteca**: abra o vídeo, preencha título/descrição, ajuste a legenda
   (offset global ou por cue), gere traduções (es/en), use "Prever sincronismo"
   e então **Publicar** (vai para `pronto`).
4. **Player**: cole o ID do vídeo e reproduza (conteúdo protegido por cookies
   assinados).
5. **Analytics**: veja a contagem de plays e o custo estimado por vídeo.

## Observações

- **Dev local** (`npm run dev` no frontend): o login e as chamadas de API
  funcionam apontando `VITE_API_BASE` para o `ApiUrl`. O **play com cookies
  assinados exige same-origin**, então teste a reprodução pela `CloudFrontUrl`
  (deployada), não pelo localhost.
- **Runtime das Lambdas**: `nodejs22.x` (traz o AWS SDK v3; sem etapa de bundle).
- **MediaConvert**: usa a fila on-demand padrão e um endpoint específico da conta
  (descoberto em runtime via `DescribeEndpoints`).
- **Tradução longa**: o endpoint de tradução é síncrono (limite de 30s do API
  HTTP). Vídeos muito longos podem exceder esse tempo — nesse caso, mover a
  tradução para um passo assíncrono (Step Functions) é o próximo passo.

## Destruir

```bash
cd infra
npx cdk destroy
```
Buckets e tabelas usam `RemovalPolicy.DESTROY` + `autoDeleteObjects` (protótipo),
então o teardown remove tudo, inclusive os vídeos.
