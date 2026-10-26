# inference-demo

A demo of an **Amazon Bedrock AgentCore Gateway** used as a **unified LLM
inference proxy**, through the zero-config `bedrock-mantle` inference target (an
OpenAI Chat Completions-/Anthropic Messages-compatible proxy, with no
per-provider credentials to manage). On top of the chat proxy it adds a full
**model evaluation** workflow: a live LLM-as-a-judge comparison, a saved
history + per-model quality benchmark, and optional managed **Amazon Bedrock
Evaluations** jobs.

Everything is private: the SPA, the streaming API, and the admin/observability
API are only reachable through **CloudFront**, and every request is gated by
**Cognito**.

- Account/region of the reference deployment: `123456789012` / `us-east-1`
- Live URL (reference deployment): `https://ded6sgmpjdova.cloudfront.net`

---

## Table of contents

- [What it demonstrates](#what-it-demonstrates)
- [Architecture](#architecture)
- [Components](#components)
- [Request flows](#request-flows)
- [Authentication](#authentication)
- [Frontend tabs](#frontend-tabs)
- [Evaluation & History (deep dive)](#evaluation--history-deep-dive)
- [Model API routing](#model-api-routing)
- [Design decisions (why)](#design-decisions-why)
- [Costs](#costs)
- [Project structure](#project-structure)
- [Deploy](#deploy)
- [Cleanup](#cleanup)

---

## What it demonstrates

1. **Unified inference** — one endpoint (the AgentCore Gateway inference target)
   proxies dozens of models (OpenAI, Anthropic, DeepSeek, Qwen, Mistral, Nova,
   Llama, etc.) with no per-provider keys.
2. **Real-time streaming** — token-by-token Server-Sent Events (SSE) from a
   FastAPI backend on Fargate.
3. **Defense in depth** — nothing is public: CloudFront + Cognito in front of
   every origin (S3, internal ALB, Lambda Function URL).
4. **Observability** — per-project / per-model token usage and inference counts
   from the `AWS/BedrockMantle` CloudWatch namespace.
5. **Model evaluation** — an inline LLM-as-a-judge to compare up to 3 models
   live (quality + speed + token + value metrics), a saved history with a
   per-model benchmark, and managed async **Bedrock Evaluations** jobs.

---

## Architecture

```
                          ┌─────────────────────────── CloudFront (single distribution) ───────────────────────────┐
                          │                                                                                          │
  User (browser)          │  default behavior     ->  S3 (SPA, private, OAC)          [static HTML/JS]               │
   │  Cognito Hosted UI    │  /api/*  behavior     ->  VPC Origin -> internal ALB      [Bearer JWT, SSE streaming]    │
   │  (PKCE login)         │  /mantle/* behavior   ->  Lambda Function URL (AWS_IAM+OAC)[X-Cognito-Token]             │
   └──────────────────────┘                                                                                          │
                          └──────────────────────────────────────────────────────────────────────────────────────┘
                                     │                              │                              │
                                     ▼                              ▼                              ▼
                            Fargate (FastAPI)              Mantle Lambda                    S3 (SPA bucket)
                             - validates user JWT           - validates Cognito token
                             - mints m2m OAuth token        - bedrock-mantle admin (projects, data retention)
                             - streams via Gateway          - CloudWatch AWS/BedrockMantle dashboards
                                     │                       - Evaluation history (S3 EvalBucket)
                                     ▼                       - starts Bedrock Evaluations jobs
                        AgentCore Gateway (MCP, JWT)                 │            │
                             │  inference target                    ▼            ▼
                             ▼  (bedrock-mantle)              S3 EvalBucket   Amazon Bedrock
                        bedrock-mantle  ->  LLM providers    (runs + jobs)    Evaluations (jobs)
```

Two independent Cognito flows on one User Pool: **interactive user login**
(Authorization Code + PKCE, public client) for the SPA, and **machine-to-machine**
(`client_credentials`, secret in Secrets Manager) for the backend → Gateway
call. See [Authentication](#authentication).

---

## Components

Everything is one CDK stack (`InferenceDemoStack`).

| # | Component | Service / type | Role |
|---|---|---|---|
| 1 | **CloudFront distribution** | `AWS::CloudFront::Distribution` | Single public entry point. Routes `/` → S3 SPA, `/api/*` → ALB (VPC Origin), `/mantle/*` → Mantle Lambda (Function URL). |
| 2 | **SPA bucket** | S3 (private, OAC, BlockPublicAccess) | Hosts the static `index.html` + a deploy-time `config.json` (Cognito settings). Reachable only via CloudFront OAC. |
| 3 | **User Pool** | Cognito | Identity for both auth flows. Self sign-up disabled (admin-created users). |
| 4 | **Resource server + m2m client** | Cognito | `client_credentials` client (with secret) + scope `inference-gateway/invoke` used by the backend to call the Gateway. |
| 5 | **Frontend client + Hosted UI domain** | Cognito | Public PKCE client for interactive login; Hosted UI at `inference-demo-<account>.auth.<region>.amazoncognito.com`. |
| 6 | **Client secret** | Secrets Manager | Stores the m2m client secret; read only by the Fargate task role. |
| 7 | **AgentCore Gateway** | `AWS::BedrockAgentCore::Gateway` (MCP, CUSTOM_JWT) | The unified inference proxy front door; authorizes the m2m JWT (client + scope). |
| 8 | **Inference target** | Custom Resource (boto3 Lambda) | Creates/removes the `bedrock-mantle` inference target on the Gateway (CloudFormation doesn't yet model the `inference` target). |
| 9 | **VPC** | EC2/VPC | Network for Fargate + ALB. Created (2 AZs, 1 NAT) or **reused** via `-c vpcId=...`. |
| 10 | **Internal ALB** | ELBv2 (internet-facing = false) | Fronts the Fargate service; no public IP. SG locked to the CloudFront VPC-Origin SG by a custom resource. |
| 11 | **Fargate service** | ECS Fargate (ARM64, 0.25 vCPU / 0.5 GB, 1 task) | FastAPI backend: validates the user JWT, mints the m2m token, streams SSE from the Gateway. |
| 12 | **Backend image** | ECR asset | Container image built locally by CDK (`backend/Dockerfile`) and pushed to ECR. |
| 13 | **Mantle Lambda** | Lambda + Function URL (AWS_IAM) + OAC | Admin/observability API under `/mantle/*`: projects, data retention, CloudWatch dashboards, Evaluation history, Bedrock eval jobs. |
| 14 | **EvalBucket** | S3 (private) | Stores Evaluation runs (`runs/…`), eval-job datasets (`jobs/…`) and job manifests (`jobmanifests/…`). Touched only by the Mantle Lambda. |
| 15 | **Eval job role** | IAM role (assumed by `bedrock.amazonaws.com`) | Service role Bedrock Evaluations assumes: read/write EvalBucket + `bedrock:InvokeModel` on the judge model. |
| 16 | **ALB SG lock** | Custom Resource (boto3 Lambda) | Restricts the ALB security group to the CloudFront VPC-Origin SG only (runs after the distribution exists). |

CloudWatch Logs are created for the Fargate task and the Lambdas. The
`AWS/BedrockMantle` CloudWatch namespace (token/inference metrics) is published
by the bedrock-mantle service itself — the app only reads it.

---

## Request flows

**Chat (streaming).** Browser `POST /api/chat/stream` (Bearer user JWT) →
CloudFront `/api/*` → internal ALB → Fargate. The backend validates the JWT,
mints an m2m OAuth token from Cognito, resolves the per-model API
([routing](#model-api-routing)), and streams SSE (`meta` → `debug` → `delta`… →
`done`) while calling the Gateway inference target. The `debug`/`done` events
carry the reconstructed Gateway request and the assembled response for the UI
debug panel.

**Admin / observability / evaluation.** Browser calls `/mantle/*` with the
Cognito access token in the `X-Cognito-Token` header (CloudFront OAC re-signs
`Authorization` for SigV4 on the Function URL). The Mantle Lambda validates the
token (JWKS + issuer + `token_use`), then talks to bedrock-mantle control APIs,
CloudWatch, S3 (EvalBucket) or Bedrock Evaluations as needed.

**Evaluation run.** The Evaluation tab runs N (≤3) parallel `/api/chat/stream`
calls, then calls the inline judge (another `/api/chat/stream` to a judge
model), then `POST /mantle/evals/runs` to persist the whole run to the
EvalBucket. The History tab reads those runs back and (optionally) starts async
Bedrock Evaluations jobs.

---

## Authentication

Two distinct Cognito flows on the same User Pool:

1. **Frontend user login (interactive).** The SPA is not open: users sign in via
   the **Cognito Hosted UI** using Authorization Code + PKCE (public client, no
   secret). The browser then sends the access token as a `Bearer` on every
   `/api/*` request; the backend validates signature (JWKS), issuer,
   `token_use`, and `client_id`. `/api/health` stays open for the ALB health
   check.
2. **Gateway auth (machine-to-machine).** The backend uses a separate
   `client_credentials` client (secret in Secrets Manager) to mint the OAuth
   token it sends to the Gateway. Unrelated to user login.

The Mantle Lambda validates the same user access token (passed as
`X-Cognito-Token`) but intentionally does **not** pin `client_id` — pinning it
would create a CDK dependency cycle (the Lambda is a CloudFront origin, and the
frontend client depends on the distribution). It is safe because the only other
client in the pool is the m2m client, whose secret never reaches the browser.

Self sign-up is disabled; the admin user is created post-deploy (see
[Deploy](#deploy)).

---

## Frontend tabs

- **Inference** — the chat UI. A project selector (from the Mantle API)
  attributes each inference to a bedrock-mantle project (`OpenAI-Project`
  header), plus a provider-grouped model picker. A collapsible debug panel shows
  latency metrics and the FE↔BE and BE↔Gateway request/response (token masked on
  screen, full in "Copy cURL").
- **Evaluation** — run the same prompt against up to 3 models in parallel and
  compare on: (1) directly-measured **speed/token metrics** (TTFT, total time,
  output tokens/s, input/output/total tokens, verbosity); (2) **quality** via an
  inline **LLM-as-a-judge** (an independent model, called through the same
  gateway, scores accuracy/completeness/relevance/clarity/instruction-following,
  then ranks and picks a winner); and (3) derived **value** metrics (quality per
  1k output tokens, quality per second). Each run is saved to S3.
- **History** — past Evaluation runs and a per-model **quality benchmark**
  (avg judge score, wins, throughput) aggregated from the saved runs. From here
  you can launch **deep evaluation** jobs on Amazon Bedrock Evaluations and
  track their status.
- **Mantle-config** — projects (list/create), CloudWatch observability
  dashboards (per-model tokens/inferences, token-usage-over-time chart) and the
  account data-retention mode.
- **Keys** — add your own **OpenAI** or **Google Gemini** API key to invoke
  those models **through the same AgentCore Gateway** (a custom provider target,
  authenticated with your key) instead of via bedrock-mantle. See
  [Direct provider keys](#direct-provider-keys-openai--gemini).
- **System-prompt** — a custom system prompt stored in the browser session and
  sent to the backend (`system_prompt`) on every inference. Pre-filled with the
  backend default (mirror of `SYSTEM_PROMPT` in `server.py`).

---

## Evaluation & History (deep dive)

There are **two** evaluation paths; they are complementary.

**Inline LLM-as-a-judge (synchronous).** Works for every gateway/mantle model,
runs live in the browser through the same `/api/chat/stream`, and powers the
Evaluation comparison + the History benchmark. Pick any model as the judge
(prefer one that is *not* a candidate to avoid self-bias — the UI warns you).

**Amazon Bedrock Evaluations (asynchronous, managed).** Rigorous, auditable
scores stored in S3. Uses a **Bedrock-native** judge model and evaluates **one
model per job** ("bring your own inference responses" mode: `taskType=General`,
one `modelIdentifier` per job). The History tab starts one job per candidate
model of a saved run and polls their status.

**Where the benchmark comes from.** The History "Model quality benchmark" is
built entirely from the saved Evaluation runs (the inline judge verdicts) — not
from Bedrock or CloudWatch. Flow: Evaluation run → inline judge verdict →
`POST /mantle/evals/runs` → object in `EvalBucket/runs/YYYY/MM/DD/…json` →
`GET /mantle/evals/runs` → the browser aggregates per model (avg overall, wins,
runs, avg tokens/s).

**EvalBucket layout (private):**

```
runs/YYYY/MM/DD/HHMMSS-<runId>.json   # one interactive Evaluation run
jobs/<runId>/<model>/dataset.jsonl    # BYOI dataset for a Bedrock eval job
jobs/<runId>/<model>/output/…         # Bedrock eval job results
jobmanifests/<ts>-<runId>.json        # index of started jobs (for status polling)
```

**Mantle endpoints (all under `/mantle/*`, same Cognito gate):**

| Method + path | Purpose |
|---|---|
| `GET /mantle/projects`, `POST /mantle/projects` | List / create bedrock-mantle projects |
| `GET/PUT /mantle/data-retention` | Read / set account data-retention mode |
| `GET /mantle/metrics` | CloudWatch dashboards (`?project=&hours=&period=`) |
| `POST /mantle/evals/runs` | Persist an Evaluation run |
| `GET /mantle/evals/runs` | List recent runs (summaries + verdicts) |
| `GET /mantle/evals/runs/{id}` | Full run detail |
| `POST /mantle/evals/jobs` | Start Bedrock eval jobs for a run (one per model) |
| `GET /mantle/evals/jobs` | List job manifests + live status |
| `GET /mantle/evals/judge-models` | Available (non-legacy) Bedrock evaluator models |

---

## Direct provider keys (OpenAI / Gemini)

Besides the zero-config `bedrock-mantle` target (which needs no keys), you can
bring your **own** OpenAI or Gemini API key and still invoke those models
**through the AgentCore Gateway** — via a **custom provider inference target**
authenticated with your key. This is the same pattern as the reference
`setup_gemini_target.py`, driven from the UI.

**How a key is added (Keys tab → `POST /mantle/keys`):**

1. The Mantle Lambda validates the key against the provider's `/v1/models` and
   **tests each candidate chat model** with a minimal real completion — only
   models the key can actually use are kept. Tests run **in parallel**
   (thread pool) so the request stays well under the CloudFront origin-response
   timeout even with many models.
2. The key is stored in **AgentCore Identity** as an **API Key Credential
   Provider** (`create_api_key_credential_provider`, API_KEY mode) — it lives in
   the token vault, not in the app.
3. A **Gateway inference target** is (re)created (`create_gateway_target` with a
   provider config: `endpoint` + `operations` mapping `/v1/chat/completions` →
   the provider path, and a `credentialProviderConfigurations` entry of type
   `API_KEY` that injects `Authorization: Bearer <key>`).
4. The tested model list (never the key) is persisted to `EvalBucket/keys/<provider>.json`.

At inference time the backend calls the Gateway exactly as before, using the
qualified model id `openai/<model>` or `gemini/<model>`; the Gateway pulls the
key from the vault and forwards the request. The key **never reaches the
browser or the backend** after it is stored. If no key is configured for a
provider, its models are **not** listed in the Inference/Evaluation pickers.

Endpoints (under `/mantle/*`, same Cognito gate): `GET /mantle/keys`,
`POST /mantle/keys` `{provider, apiKey}`, `DELETE /mantle/keys/{provider}`.

### Where the key is actually stored (and the IAM it needs)

AgentCore Identity credential providers are **backed by AWS Secrets Manager**
(native integration): `CreateApiKeyCredentialProvider` creates a secret
(name prefix `bedrock-agentcore...`) in your account to hold the key, and the
Gateway reads that secret at inference time to inject the outbound
`Authorization` header. So the key *is* managed by AgentCore Identity — Secrets
Manager is just the backing store. Two roles therefore need Secrets Manager
access, scoped to the AgentCore-owned secrets only (never the Cognito m2m
secret):

| Principal | Permissions | Why |
|---|---|---|
| **Mantle Lambda** role | `bedrock-agentcore:*`; `secretsmanager:CreateSecret`/`PutSecretValue`/`UpdateSecret`/`TagResource`/`DescribeSecret`/`DeleteSecret`/`*ResourcePolicy` on `secret:bedrock-agentcore*` | Create/delete the credential provider + Gateway target; write the backing secret. No `GetSecretValue` (never needs to read the key back). |
| **Gateway** role | `bedrock-agentcore:GetResourceApiKey` (+ workload-token reads); `secretsmanager:GetSecretValue` on `secret:bedrock-agentcore*` | Retrieve the vaulted key at inference time to call the provider. |

If your account provisions these secrets under a different name prefix, widen
the resource scope accordingly (otherwise create/retrieve will `AccessDenied`).

## Model API routing

bedrock-mantle exposes models through three different OpenAI-/Anthropic-
compatible APIs, and each model accepts only ONE of them. Rather than probing at
runtime, the backend routes deterministically from the model id (format
`<target>/<provider>.<model>`) using a static map in `server.py`
(`PROVIDER_API` + `MODEL_API_OVERRIDES` + `pick_api()`). To support a new model,
update that map.

| API | Endpoint | Models |
|---|---|---|
| Responses | `/v1/responses` | `openai.gpt-5*`, `openai.gpt-oss-120b/20b` |
| Messages (Anthropic) | `/v1/messages` | `anthropic.claude-*` |
| Chat Completions | `/v1/chat/completions` | everyone else (default): `deepseek.*`, `google.gemma-3-*`, `minimax.*`, `mistral.*`, `moonshotai.*`, `nvidia.nemotron-*`, `qwen.*`, `writer.*`, `zai.*`, `openai.gpt-oss-safeguard-*` |

Notes: Anthropic Claude models only work via the Messages API and cannot be
attributed to a project (the Messages API rejects the `OpenAI-Project` header),
so they always stay under `default`. Some models return `access_denied`
("not enabled for this account") regardless of API — that's an account
entitlement, not a routing issue.

---

## Design decisions (why)

**Why a backend, not the SPA calling the Gateway directly?** The Gateway uses
OAuth `client_credentials`, which needs a `client_secret` — unsafe in the
browser. The secret lives in Secrets Manager, read only by the backend.

**Why Fargate and not Lambda?** The backend does token-by-token **SSE
streaming**. Lambda with the Python runtime has no native response streaming, so
a long-lived process behind an ALB is the simplest way to hold the connection
open and push bytes as they arrive. (The Mantle admin API has no streaming, so
it *is* a Lambda.)

**Why is the ALB internal?** It never faces the internet. CloudFront reaches it
through a **VPC Origin** (`AWS::CloudFront::VpcOrigin`) inside the VPC, and a
custom resource locks the ALB security group to the CloudFront-managed origin SG
— no `0.0.0.0/0` ingress.

**Why a custom resource for the inference target?**
`AWS::BedrockAgentCore::GatewayTarget` today only models the `Http`/`Mcp`
formats; the `inference` format (used by `bedrock-mantle`) is not in the
CloudFormation schema yet, though the service API accepts it. A thin boto3
Lambda calls the real API; when CloudFormation adds `inference`, it can become a
plain `CfnGatewayTarget`.

**Why CDK (not SAM)?** The core resources (Gateway, Cognito, VPC/Fargate/ALB,
CloudFront) have first-class CDK constructs; SAM is optimized for Lambda + API
Gateway and doesn't cover this mix well.

**Inline judge vs. Bedrock Evaluations** — see
[Evaluation & History](#evaluation--history-deep-dive): inline is live and
covers all gateway models; Bedrock is async, managed and auditable but
Bedrock-native-judge + one model per job.

---

## Costs

> Figures are **approximate**, `us-east-1`, on-demand, and change over time —
> always confirm with the [AWS Pricing Calculator](https://calculator.aws) and
> current service pricing. The point here is the **relative** weight and which
> resources bill you **even with zero traffic**.

### Resources that cost money even when idle (always-on)

These run 24/7 once deployed, regardless of whether anyone uses the app:

| Resource | Driver | Approx. idle cost (us-east-1) |
|---|---|---|
| **NAT Gateway** (only on the *create-VPC* path, 1 NAT) | ~$0.045/hr + $0.045/GB processed | **~$32 / month** + data |
| **Application Load Balancer** (internal) | ~$0.0225/hr + LCU | **~$16 / month** + LCU |
| **Fargate task** (1 task, 0.25 vCPU / 0.5 GB, always running) | ~$0.0123/hr (vCPU+GB) | **~$9 / month** |
| **Secrets Manager** (1 secret + 1 per configured direct key) | $0.40/secret/month + API calls | **~$0.40–1.20 / month** |
| **ECR** (backend image) | $0.10/GB-month | **cents** |
| **S3** (SPA + EvalBucket, at rest) | $0.023/GB-month | **cents** |
| **CloudWatch Logs** (stored task/Lambda logs) | $0.03/GB-month stored | **cents**, grows with logs |
| **Route 53 / EIP / Cognito / CloudFront** | — | **~$0** idle (Cognito free tier; CloudFront and Lambda are pay-per-use; the NAT's EIP is in-use so not charged) |

**Ballpark idle total: ~$55–60 / month**, dominated by the **NAT Gateway** and
the **ALB**. If you **reuse an existing VPC** (`-c vpcId=...`), this stack
creates **no NAT** — you inherit that VPC's networking cost instead (which may
be $0 if it only uses an Internet Gateway / shared NAT). The reference
deployment reuses `vpc-74e3ab0e`, so it has no NAT charge from this stack.

**Cutting the idle cost:**

- **Remove the NAT** by adding VPC Interface Endpoints for ECR (api + dkr),
  Secrets Manager, CloudWatch Logs and the Gateway/Bedrock endpoints, then place
  Fargate in isolated subnets. More resources, but no NAT hourly/GB cost.
- **Scale Fargate to 0** when not demoing (`desired_count=0`), or **destroy**
  the stack between demos (`npx cdk destroy`) — the biggest savings, since it
  removes the NAT + ALB + Fargate together.
- The ALB is required as long as the backend is on Fargate; moving to Lambda
  (only viable if SSE streaming is dropped) would remove both the ALB and the
  NAT.

### Usage-based costs (only when used)

- **LLM inference** through the Gateway / bedrock-mantle — billed per input/
  output token, varies a lot by model. This is normally the dominant cost under
  real use.
- **Amazon Bedrock Evaluations jobs** — each "deep eval" job runs the judge
  model over your data; billed as judge-model inference per job. Starting jobs
  for 3 candidate models = 3 jobs. Can add up; start them deliberately.
- **AgentCore Gateway** — consult current AgentCore pricing (primarily
  usage-based per request/invocation).
- **CloudFront / NAT data transfer**, **CloudWatch GetMetricData** (dashboards),
  and **Lambda invocations** — all small and proportional to use.

### Data-retention / privacy note

Enabling account data-retention `provider_data_share` (Mantle-config tab) is
account-wide: it sends prompts/responses to the model provider (leaves AWS's
data boundary, ~30-day retention) and is required for some Mythos-class models.
It's a privacy setting, not a direct dollar cost — but treat it deliberately.

---

## Project structure

```
inference-demo/
  backend/
    server.py          # FastAPI: JWT validation + m2m OAuth token + SSE streaming; model API routing; debug/gateway_response events
    Dockerfile
    requirements.txt
  backend_mantle/
    handler.py         # Lambda: projects, data retention, CloudWatch dashboards, Evaluation runs/jobs, judge-models (Cognito-gated)
    requirements.txt
  frontend/
    index.html         # static SPA: sidebar (Inference / Evaluation / History / Mantle-config / System-prompt), PKCE login
  infra/
    app.py
    create-admin-user.sh             # post-deploy: creates the Cognito admin user
    list-vpcs.sh                     # inspect VPC quota + find a reusable VPC
    inference_infra/
      stack.py                       # the whole stack (Cognito, Gateway, Fargate/ALB, CloudFront, Mantle Lambda, EvalBucket, IAM)
      custom_resources/
        inference_target/handler.py   # creates/removes the inference target (boto3)
        alb_sg_lock/handler.py        # locks the ALB SG to the CloudFront VPC-origin SG
  .env.example
```

---

## Deploy

Prerequisites: Python 3.11+, Node.js, **Docker** (required — the CDK builds the
backend image locally and pushes it to ECR), valid AWS credentials.

### Docker: why it's needed, and how to check it

The backend runs on **Fargate**, which runs container images. During
`cdk deploy`, the CDK runs `docker build` on `backend/` and pushes the image to
ECR. So the Docker daemon must be running **before** you deploy.

```bash
docker info >/dev/null 2>&1 && echo "Docker is running" || echo "Docker is NOT running"
```

Docker Desktop (macOS): `open -a Docker` then wait for the daemon. Some managed
macOS environments require signing in to Docker Desktop first.

Alternative — colima: `brew install colima docker && colima start`. No project
changes are needed; the CDK just needs a working Docker daemon on the standard
socket. (The reference deployment builds ARM64 images and uses colima.)

**1. Deploy the infrastructure.**

```bash
cp .env.example .env        # fill in your credentials and do NOT commit it
set -a && source .env && set +a   # export the AWS credentials into the shell

cd infra
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm install                 # installs the pinned CDK CLI (see package.json)

npx cdk bootstrap    # first time in the account/region
npx cdk deploy
```

The `.env` in the reference deployment uses `export KEY=value` lines; a common
one-liner to load only the vars (stripping `export`) for a single command:

```bash
env $(sed -E '/^#/d;/^$/d;s/^export +//' .env | xargs) npx cdk deploy -c vpcId=vpc-74e3ab0e --require-approval never
```

Two things keep the CDK toolchain reproducible:

- `cdk.json` runs the app with `.venv/bin/python`, so the CDK CLI always uses
  this virtualenv regardless of your shell's default `python3`. The venv must
  live at `infra/.venv`.
- `package.json` pins the `aws-cdk` CLI to a version compatible with
  `aws-cdk-lib`, so `npx cdk` uses it instead of any older global CLI.

This takes longer than a Lambda-only stack (Docker image build + VPC + Fargate +
ALB).

#### Reusing an existing VPC (VPC-per-region limit)

By default the stack creates a new VPC. Accounts have a soft limit of 5 VPCs per
region, so `cdk deploy` can fail with `The maximum number of VPCs has been
reached.` Inspect candidates with the helper (run from `infra/` with AWS creds
exported; targets `$AWS_REGION`, default `us-east-1`):

```bash
./list-vpcs.sh
```

It prints the VPC quota and only the **suitable** VPCs (private subnets with
egress across ≥ 2 AZs) and their qualifying subnets. Then either reuse one:

```bash
npx cdk deploy -c vpcId=vpc-0123456789abcdef0     # or set EXISTING_VPC_ID
```

…or free up quota (delete an unused VPC / request a limit increase) and deploy
normally. A reused VPC must have private subnets **with egress** (NAT or the
relevant VPC endpoints) across ≥ 2 AZs so Fargate can reach
ECR/Secrets Manager/Cognito/Gateway.

**2. Create the admin user** (post-deploy — the User Pool must exist). The
helper reads the `UserPoolId` output, creates the user idempotently, and sets a
**permanent** password:

```bash
./create-admin-user.sh                                    # defaults: admin@example.com / Admin123!
# or, for a real login:
ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='S3cret-pass!' ./create-admin-user.sh
```

Re-running the script resets the password.

**3. Open the app.** Browse to the `SiteUrl` output, sign in through the Cognito
Hosted UI, and start chatting.

---

## Cleanup

```bash
cd infra
npx cdk destroy
```

Destroying removes the always-on cost (NAT if created, ALB, Fargate) — the
fastest way to stop charges between demos. Both S3 buckets have
`autoDeleteObjects` + `RemovalPolicy.DESTROY`, so the SPA and Evaluation history
are deleted with the stack; export anything you want to keep first. In-flight or
completed **Bedrock Evaluations** jobs and their results live in the Bedrock
service (and the EvalBucket) — check the Bedrock console if you started deep
evals.
