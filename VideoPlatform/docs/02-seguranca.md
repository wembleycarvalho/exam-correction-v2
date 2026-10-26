# Segurança — VideoPlatform (sem DRM)

Objetivo: impedir download indevido e compartilhamento de URL sem login,
usando uma arquitetura profissional **sem DRM** nesta fase. DRM é tratado
separadamente em `docs/03-drm.md`.

## 1. Princípios

1. **Nada é público.** Os buckets S3 bloqueiam todo acesso público.
2. **Só o CloudFront lê o S3** (Origin Access Control — OAC). Não existe URL
   do S3 que funcione direto.
3. **Só quem logou acessa o conteúdo.** O CloudFront exige **cookies assinados**,
   emitidos pelo backend apenas após autenticação no Cognito.
4. **Acesso curto e revogável.** Os cookies têm TTL curto; expirado, o player
   precisa de uma nova autorização.
5. **Defesa em camadas.** WAF, HTTPS obrigatório, CORS restrito, headers de
   segurança e, opcionalmente, geo-restrição.

## 2. Como cada requisito é atendido

### "Vídeos não podem ficar expostos diretamente"
- Bucket privado + `BlockPublicAccess` total.
- Policy do bucket só permite o *principal* do CloudFront (OAC) via
  `aws:SourceArn` da distribuição.
- Resultado: a URL `https://<bucket>.s3.amazonaws.com/...` responde `403`.

### "Impedir compartilhar a URL sem passar pelo login"
- O player nunca recebe uma URL "aberta". Ele recebe a URL do CloudFront **mais**
  três cookies assinados (`CloudFront-Policy`, `CloudFront-Signature`,
  `CloudFront-Key-Pair-Id`).
- Os cookies são emitidos por `POST /play/{videoId}` **somente** com um JWT válido
  do Cognito e `status = pronto`.
- Se alguém copiar só a URL do manifesto e mandar pra outra pessoa, sem os cookies
  (ou com cookies expirados) o CloudFront devolve `403`.
- Como o cookie é marcado `HttpOnly`, `Secure` e `SameSite`, não é lido por JS de
  terceiros nem viaja fora do domínio.

### "Impedir downloads indevidos"
- Com HLS, o "vídeo" são centenas de segmentos protegidos pelos mesmos cookies de
  curta duração; não há um arquivo único clicável para baixar.
- `Content-Disposition` e headers de resposta desencorajam salvar.
- WAF com *rate limiting* bloqueia varredura/baixa em massa de segmentos.

> **Limite honesto (importante):** sem DRM, um usuário tecnicamente determinado
> ainda pode, enquanto a sessão está válida, capturar os segmentos e remontar o
> vídeo (ferramentas de linha de comando, extensões, captura de tela). O que esta
> arquitetura garante é: nada público, nada acessível sem login, links expiram e
> não há download "de um clique". Proteção forte contra cópia exige DRM — ver
> `docs/03-drm.md`.

## 3. Fluxo de autorização do play

```
Frontend (logado)
   │  JWT (Cognito) no Authorization header
   ▼
POST /play/{videoId}
   │  Lambda:
   │   1. valida JWT (authorizer Cognito)
   │   2. confirma status = "pronto"
   │   3. (analytics) ADD playCount 1 + grava evento em Plays
   │   4. gera cookies assinados CloudFront (TTL curto, escopo do videoId)
   ▼
Set-Cookie: CloudFront-Policy / -Signature / -Key-Pair-Id  (HttpOnly, Secure)
   │
   ▼
Shaka Player pede master.m3u8 + segmentos ao CloudFront COM os cookies
   ▼
CloudFront valida assinatura na borda → serve do S3 (OAC) ou 403
```

## 4. Autenticação (Cognito)

- User Pool com login por e-mail/senha. Todos os usuários são admin nesta fase
  (sem grupos/papéis).
- A SPA usa o fluxo OAuth2 (Hosted UI ou SDK Amplify/Cognito) e guarda o token em
  memória (evitar `localStorage` para o token de acesso).
- A API Gateway usa um **JWT authorizer** nativo do Cognito; nenhuma rota de
  conteúdo responde sem token válido.

## 5. CloudFront — configuração de segurança

- **OAC** (substitui o legado OAI) para ler o S3 privado.
- **Trusted Key Group**: uma chave pública cadastrada; o backend assina com a
  chave privada (guardada em **AWS Secrets Manager** / **SSM Parameter Store**,
  nunca no código).
- **Viewer protocol policy**: `redirect-to-https` (HTTPS obrigatório).
- **Response Headers Policy**: HSTS, `X-Content-Type-Options`, `Referrer-Policy`,
  CSP adequada ao player.
- **AWS WAF**: regras gerenciadas (Common, Known Bad Inputs) + *rate limit* por IP.
- **Geo-restrição**: opcional (habilitar se o conteúdo for regional).

### 5.1 O que o WAF cobre (e o que não cobre) contra pirataria

O WAF ajuda contra pirataria, mas num pedaço **estreito** do problema: ele não
protege o conteúdo em si, protege o **caminho** até ele. Importante não se iludir
com o alcance dele.

**O que ele cobre:**
- **Freia a coleta automatizada em massa** (o ponto mais relevante). Sem DRM, o
  ataque clássico de "baixar o vídeo" é um script que lê o manifesto HLS e puxa
  todos os segmentos em sequência. O *rate limit* por IP corta exatamente isso:
  puxar centenas de segmentos muito rápido estoura o limite e passa a tomar
  bloqueio. Atrapalha muito quem quer "ripar o catálogo inteiro".
- **Protege os endpoints sensíveis, não só os bytes.** O `POST /play/{videoId}`
  (que emite os cookies assinados) e a API em geral são alvos. Regras gerenciadas
  + rate limit reduzem brute force, enumeração de `videoId`, payloads malformados
  e tentativas de achar brecha para burlar a autorização.
- **Dá visibilidade / sinal de anomalia.** Os logs do WAF mostram "um IP puxando
  milhares de segmentos" — telemetria que alimenta **detecção** de pirataria e
  combina com o watermarking (`docs/05-watermarking.md`): o WAF aponta o
  comportamento, o watermark aponta a identidade.
- **Bloqueio de origem conhecida.** IP/faixa/geo de um scraper já identificado
  pode ser barrado direto.

**O que ele NÃO cobre (limite honesto):**
- **Não impede o usuário autorizado.** Um usuário logado, com cookies válidos,
  assistindo em ritmo normal, é **indistinguível** de um player legítimo. Esse é o
  principal vetor de pirataria (o atacante é o próprio assinante) — e o WAF é cego
  para ele.
- **Não descriptografa nada.** Impedir decodificar é DRM (`docs/03-drm.md`).
- **Não atribui vazamento.** Saber *quem* vazou é watermarking
  (`docs/05-watermarking.md`).
- **É um quebra-molas, não um muro.** Rate limit é por IP e grosseiro: dá para
  "andar devagar" ficando abaixo do limite, ou distribuir entre vários IPs.
  Atrasa e expõe o atacante preguiçoso; não para o determinado.

**Onde ele encaixa nas camadas:**

| Camada | Pergunta que responde |
|--------|-----------------------|
| OAC + cookies assinados + Cognito | **quem** recebe os bytes |
| **AWS WAF** | **com que velocidade/volume**, e protege os endpoints de abuso/varredura |
| DRM (`03`) | se conseguem **decodificar** os bytes |
| Watermarking (`05`) | **quem vazou** depois |

> **Resumo:** contra pirataria, o WAF vale por **frear a ripagem automatizada em
> massa e blindar o endpoint de autorização**, além de gerar sinal para detecção —
> mas não faz nada contra o usuário autorizado nem contra a extração do vídeo, que
> são os problemas que exigem DRM e watermarking.

## 6. Rotação e segredos

- Chave privada de assinatura do CloudFront em Secrets Manager; rotação via novo
  par de chaves + atualização do Key Group (sem downtime, aceitando as duas por um
  período).
- Credenciais AWS fora do repositório (`.env` no `.gitignore`).

## 7. Checklist de segurança (fase sem DRM)

- [ ] Buckets com `BlockPublicAccess` total e sem ACLs públicas.
- [ ] Policy do bucket restrita ao OAC da distribuição.
- [ ] CloudFront com Trusted Key Group e HTTPS obrigatório.
- [ ] Cookies assinados `HttpOnly`/`Secure`/`SameSite` com TTL curto.
- [ ] JWT authorizer do Cognito em todas as rotas de conteúdo.
- [ ] WAF com rate limiting ativo.
- [ ] Chave privada de assinatura em Secrets Manager (não no código).
- [ ] CORS restrito ao domínio do frontend.
- [ ] Logs de acesso do CloudFront habilitados (auditoria).
