# DRM — Guia de decisão (quando/como adicionar)

Esta plataforma **começa sem DRM**. A proteção atual (bucket privado + OAC +
cookies assinados de curta duração + WAF + login) está descrita em
`docs/02-seguranca.md`. Este documento explica o que o DRM acrescenta, quanto
custa e o quanto complica a arquitetura, para você decidir se/quando ligar.

## 1. O que é DRM, afinal

DRM (Digital Rights Management) criptografa o vídeo de forma que **só um player
autorizado, em um dispositivo autorizado, consiga descriptografar na hora de
tocar** — e a chave nunca fica acessível ao usuário. Diferente dos cookies
assinados (que controlam *quem baixa os bytes*), o DRM controla *quem consegue
decodificar os bytes*. Mesmo que a pessoa capture os segmentos, eles ficam
inúteis sem a licença.

Os três sistemas de DRM que cobrem o mercado:

| Sistema    | Dono       | Onde domina |
|------------|------------|-------------|
| Widevine   | Google     | Chrome, Android, Firefox, Edge |
| FairPlay   | Apple      | Safari, iOS, macOS, tvOS |
| PlayReady  | Microsoft  | Windows, Edge, Xbox, muitas Smart TVs |

Para cobrir "a web toda" você precisa dos três. Com **CMAF + CENC (cbcs)** dá
para empacotar **um único conjunto de arquivos** criptografados e servir as três
licenças diferentes — sem reencode triplo. O Shaka Player (já escolhido) fala os
três via EME.

## 2. Vantagens do DRM

- **Proteção real contra cópia/redistribuição.** É a única forma de impedir que
  um usuário autenticado extraia o vídeo em claro. Sem DRM, enquanto a sessão é
  válida, os segmentos podem ser remontados.
- **Exigência de parceiros/estúdios.** Conteúdo premium licenciado quase sempre
  obriga DRM contratualmente.
- **Regras por licença.** Dá para impor saída HDCP, janelas de tempo, limite de
  dispositivos, bloqueio de output analógico, etc.
- **Dissuasão forte.** Eleva muito a barreira: já não é "abrir o DevTools e
  baixar o .ts".

## 3. Desvantagens / custos ocultos

- **Nunca é 100%.** DRM eleva o custo do ataque, não o zera (ex.: captura por
  HDMI/placa, re-filmagem de tela). Promete "muito mais difícil", não
  "impossível".
- **Complexidade operacional alta** (ver seção 5).
- **Dependência de licenciador de chaves** (serviço terceiro ou AWS parceiro).
- **Compatibilidade e QA.** Cada combinação navegador × SO × versão vira caso de
  teste. FairPlay no Safari tem particularidades (certificado da Apple, formato
  de licença próprio).
- **Fricção para o usuário.** Navegadores sem o módulo CDM, ambientes
  corporativos restritos, Linux sem Widevine L3 atualizado etc. podem falhar o
  play.
- **Custo recorrente** (ver seção 4).

## 4. Custos estimados (ordem de grandeza — validar na contratação)

DRM adiciona dois tipos de custo além do que já existe:

1. **Empacotamento criptografado.** No AWS Elemental MediaConvert, a criptografia
   DRM usa **SPEKE** (Secure Packager and Encoder Key Exchange). O MediaConvert em
   si cobra pelos mesmos minutos de saída; o custo novo é o **servidor de chaves**.

2. **Serviço de chaves/licenças (DRM key provider).** Duas rotas:
   - **SaaS multi-DRM** (ex.: EZDRM, Axinom, BuyDRM/KeyOS, Pallycon). Modelos
     comuns: mensalidade mínima + preço por licença emitida (frequentemente na
     casa de **US$ 0,004–0,02 por licença**, ou pacotes mensais a partir de
     ~**US$ 50–500/mês** dependendo do fornecedor e volume). Uma "licença" é
     emitida por sessão de play por dispositivo.
   - **Self-hosted** (seu próprio servidor de licença). Elimina a taxa por
     licença, mas exige credenciais oficiais de cada DRM (Widevine via Google,
     FairPlay via Apple, PlayReady via Microsoft) e muito mais engenharia e
     manutenção. Raramente vale para um protótipo.

   > Valores de mercado mudam e variam muito por fornecedor/volume. Trate os
   > números acima como ponto de partida para cotação, não como preço fechado.

3. **Infra adicional** (endpoint de licença, Secrets, logs) — pequeno perto do
   item 2.

Comparativo rápido com a fase atual (sem DRM): hoje o custo marginal de
proteção é ~zero (OAC e cookies assinados não têm cobrança própria relevante).
Ligar DRM introduz um **custo recorrente por play** e/ou **mensalidade**.

## 5. Impacto na arquitetura (complexidade)

O que muda em relação ao diagrama atual:

```
            SEM DRM (hoje)                    COM DRM (futuro)
──────────────────────────────   ──────────────────────────────────────────
MediaConvert → HLS em claro       MediaConvert + SPEKE → HLS/CMAF CRIPTOGRAFADO
                                        │
                                        ├─ (novo) DRM Key Provider  (SPEKE)
CloudFront + cookies assinados    CloudFront + cookies assinados (continua)
                                        │
Shaka toca direto                 Shaka + (novo) requisição de LICENÇA ao
                                   License Server por sessão (Widevine/FairPlay/
                                   PlayReady), com token de autorização
```

Itens novos a construir/operar:
- **Integração SPEKE** no job do MediaConvert (perfil de criptografia, keyIds).
- **DRM Key/License Server** (SaaS ou próprio) com endpoint de licença.
- **Proxy de licença autenticado**: a licença só deve ser emitida para sessão
  logada (reaproveita o JWT do Cognito) — nova rota tipo `POST /drm/license`.
- **Configuração de EME no Shaka** por sistema de DRM, incluindo o **certificado
  da Apple** para FairPlay.
- **Matriz de testes** navegador × SO ampliada.
- **CMAF cbcs** como formato de saída (unifica os três DRMs em um empacotamento).

## 6. Recomendação

- **Fase atual (protótipo):** manter **sem DRM**. A combinação de bucket privado,
  OAC, cookies assinados de TTL curto, WAF e login já entrega uma proteção
  profissional contra os cenários mais comuns (link vazado, acesso sem login,
  download de um clique), com custo marginal próximo de zero.
- **Quando migrar para DRM:** se/quando houver (a) conteúdo premium ou licenciado
  que exija contratualmente, ou (b) evidência de pirataria relevante, ou (c)
  requisito de bloqueio de saída (HDCP). Nesse momento, por já termos escolhido
  **HLS/CMAF + Shaka Player**, a migração é incremental: adiciona-se SPEKE no
  encode, um license server e a rota de licença — **sem trocar player nem
  refazer o frontend**.

## 7. A verdade incômoda — como se contorna DRM (threat model)

Esta seção existe para evitar uma ilusão cara: **ligar DRM não torna o download
impossível**. As técnicas abaixo são **publicamente conhecidas, documentadas e,
em vários casos, automatizadas**. DRM eleva o custo e reduz o número de pessoas
capazes de piratear — é dissuasão e conformidade contratual, não um cofre.

### 7.1 O "buraco analógico" (insolúvel por definição)
O vídeo precisa virar luz numa tela e som num alto-falante. A partir daí:
- **Captura HDMI** com placa que ignora/remove HDCP. HDCP 1.4 (até 1080p) é
  removido por *splitters* baratos de prateleira; HDCP 2.2 (4K) é mais difícil,
  mas há *strippers*. Captura limpa até 1080p é barata e confiável.
- **Filmar a tela** com câmera: perda de qualidade, mas nenhum DRM impede.
- **Gravadores de tela**: o *protected media path* (Windows + PlayReady em
  hardware) entrega frame preto para muitos gravadores — mas depende do nível de
  segurança; no caminho de software comum do desktop nem sempre bloqueia.

### 7.2 Widevine L3 — o vetor que mais importa aqui
Widevine tem três níveis de segurança:
- **L1**: cripto *e* decode dentro do TEE (chip seguro). Mais forte.
- **L2**: cripto no TEE, decode fora.
- **L3**: tudo em software, sem raiz de confiança em hardware.

No **Chrome/Firefox desktop o padrão é L3**. O CDM de L3 já foi
engenharia-reversa e chaves de dispositivo vazaram publicamente; existe
ferramental aberto que recupera a *content key* a partir da própria troca de
licença L3. Com a chave, descriptografa-se os segmentos CENC/CMAF **offline** com
ferramentas padrão. É conhecimento comoditizado — a base de boa parte dos "stream
rippers".

> **Implicação direta:** se o conteúdo tocar em L3 (quase inevitável para ter
> alcance), o DRM é contornável com ferramenta pública e esforço modesto. Forçar
> **L1/hardware** eleva muito a barra, mas obriga a **recusar playback em L3** —
> quebrando Linux, muitos desktops e ambientes corporativos. É um trade-off direto
> entre segurança e alcance.

### 7.3 Demais sistemas
PlayReady (SL3000 em hardware) e FairPlay (preso ao hardware Apple) são
geralmente mais duros. Mas PlayReady em software (SL2000) já teve comprometimento,
e o buraco analógico + HDCP stripping se aplicam a todos.

### 7.4 O atacante autorizado
DRM **não impede** que um usuário legítimo e logado capture pelo buraco analógico.
Com frequência o "inimigo" é o próprio assinante — cenário que nenhum DRM resolve.

### 7.5 Dado empírico que fecha o argumento
Grupos de pirataria ripam catálogos de grandes serviços de streaming
rotineiramente — e esses usam DRM em **hardware** (L1/SL3000). Se o estado da arte
com orçamento de estúdio vaza, nosso conteúdo não é mais especial.

**Conclusão honesta:** sim, mesmo com DRM dos três sistemas, o conteúdo ainda pode
ser baixado; as estratégias são conhecidas; e, no fim do dia, se alguém quiser
muito, haverá vazamento. O objetivo realista do DRM é cortar o atacante casual e
os scrapers automáticos, não eliminar a pirataria.

## 8. O que de fato reduz o dano (complementos ao DRM)

Contra "alguém vai conseguir baixar", a ferramenta honesta não é *mais* DRM:

- **Watermarking forense por sessão** (o complemento mais importante): marca
  invisível com o id do usuário/sessão embutida no stream. Não impede a cópia,
  mas permite **identificar quem vazou** a partir do arquivo capturado — a única
  resposta real ao atacante autorizado, e muitas vezes mais valiosa que o DRM.
  Fornecedores: Irdeto, NAGRA, Verimatrix, entre outros. Adiciona custo e
  complexidade (variantes A/B no CDN ou composição no cliente).
  **Tratado em detalhe em `docs/05-watermarking.md`** (tipos, mecanismo A/B,
  encaixe na arquitetura, custos e limites).
- **Enforce de HDCP** na licença (bloqueia a captura HDMI mais fácil; *strippers*
  ainda existem, mas sobe a barra).
- **Forçar nível de DRM em hardware** (L1/SL3000) para conteúdo de alto valor,
  aceitando a perda de alcance.
- **Limites operacionais**: concorrência por conta, limite de dispositivos, TTL
  curto de licença, teto de downloads offline.
- **Detecção de anomalia** nos padrões de acesso/segmentos (reaproveita o WAF e os
  logs já previstos).
- **Processo legal / takedown** para o conteúdo que inevitavelmente escapar.

## 9. Resumo em uma frase

Sem DRM: "ninguém de fora entra, links expiram, não dá pra baixar com um clique".
Com DRM: "a barra sobe muito, mas o conteúdo ainda é extraível por técnicas
conhecidas (L3 em software, buraco analógico/HDMI) — então trate DRM como
dissuasão + conformidade, e combine com **watermarking forense** para rastrear
quem vazar".
