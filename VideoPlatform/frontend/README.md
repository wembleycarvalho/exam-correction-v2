# Frontend — VideoPlatform

SPA em React + Vite + TypeScript. Hash routing. Player **Shaka** (ABR HLS +
legenda WebVTT). Login via **Cognito** (SRP, `amazon-cognito-identity-js`).

## Menus

- **Upload** — upload multipart direto ao S3 (sem limite de tamanho) com barra de
  progresso e acompanhamento do status de processamento.
- **Biblioteca** — lista de vídeos; abrir um item mostra o painel de revisão:
  título/descrição, editor de **sincronismo de legenda** (offset global e por
  cue), **tradução** (es/en), **pré-visualização** com o player e **publicação**
  (`revisar → pronto`).
- **Player** — informe o ID do vídeo; o backend autoriza e emite cookies
  assinados; o Shaka reproduz via CloudFront.
- **Analytics** — contagem de plays por vídeo e custo estimado de processamento.

## Configuração

Em produção, o `/config.js` servido pelo CloudFront define `apiBase` (vazio =
same-origin), `region`, `userPoolId` e `userPoolClientId`. O script
`scripts/deploy-frontend.sh` injeta esses valores automaticamente.

Em desenvolvimento, copie `.env.example` para `.env` e preencha com o `ApiUrl` e
os IDs do Cognito (outputs da stack):

```bash
cp .env.example .env
# edite os valores
npm install
npm run dev
```

> O play com cookies assinados exige same-origin; teste a reprodução pela URL do
> CloudFront (deploy), não pelo `localhost`.

## Build

```bash
npm run build   # tsc --noEmit + vite build -> dist/
```
