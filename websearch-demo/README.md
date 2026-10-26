# websearch-demo

Minimalist demo of an **AgentCore Gateway** with a target of type **native
MCP connector "Web Search Tool"** (100% managed by AWS: no Lambda, no API
key, no search infrastructure to maintain).

```
User -> Cognito Hosted UI (sign in)            [browser redirect, PKCE]
     -> CloudFront -> S3 (SPA)                  [static content]
                   -> Lambda Function URL       [/api/*, thin backend]
                          -> validates user token (cognito-idp:GetUser)
                          -> Cognito (M2M OAuth token, client_credentials)
                          -> AgentCore Gateway (/mcp) -> Web Search Tool
```

## Authentication

There are **two independent auth layers**, backed by the same Cognito User
Pool but by two different app clients:

1. **User login (frontend).** Users sign in through the Cognito **Hosted UI**
   using the OAuth **Authorization Code + PKCE** flow, via a public app
   client (no secret — safe for the browser). Self sign-up is **disabled**:
   accounts are created by an admin (see below). The SPA sends the user's
   access token as `Authorization: Bearer <token>` on every `/api/search`
   call, and the Lambda validates it (`cognito-idp:GetUser`) before doing
   anything.

2. **Backend-to-Gateway (M2M).** The Lambda authenticates to the AgentCore
   Gateway with the OAuth **client_credentials** flow, using a separate app
   client whose secret lives in Secrets Manager. This is unchanged from the
   backend-only design below.

The PKCE token exchange and logout are proxied/redirected through the backend
and Hosted UI respectively — the browser never makes a cross-origin `fetch`
to Cognito's `/oauth2/token` or `/logout`, because those endpoints don't
reliably support CORS for browser-initiated calls.

## Why this architecture

### Why a backend, instead of the SPA talking directly to the Gateway?

The Gateway uses OAuth `client_credentials` on Cognito, which **requires a
client_secret**. A client_secret can't be kept safe in an app that runs in
the browser — anyone can open devtools and read the JavaScript code,
extracting the secret. That's why:

- The client_secret lives in **Secrets Manager**, read only by the Lambda at
  runtime.
- The browser only talks to **this backend** (same origin via CloudFront,
  so no CORS is even needed), never directly with Cognito/Gateway.

**Alternative considered and discarded:** giving browser credentials direct
access to the Gateway via a Cognito Identity Pool (temporary AWS
credentials, SigV4 signing in the JS itself, gateway with `authorizerType:
AWS_IAM`). Technically possible, but it requires implementing SigV4 signing
in JavaScript and widens the exposure surface of AWS credentials in the
browser — complexity and risk that don't pay off for a small demo. If you
ever want this "backend-less" route, the starting point is switching the
Gateway's `authorizerType` to `AWS_IAM` and using
`@aws-sdk/credential-providers` (Cognito Identity Pool) + SigV4 signing on
the frontend.

### Why Lambda (and not Fargate)?

The call to the `WebSearch` tool is **a single request/response** — there's
nothing to "stream". A Lambda behind a Function URL is the simplest,
cheapest (pay per invocation) and lowest-operational-overhead option (no
container, no ALB, no VPC) for this usage pattern.

### Why are Lambda and S3 never exposed directly to the internet?

- The **S3 bucket** is private (`BLOCK_ALL`, no public website hosting);
  only CloudFront can access it, via Origin Access Control (OAC).
- The **Lambda Function URL** uses `AuthType=AWS_IAM` + a Function URL OAC;
  only the CloudFront distribution has permission (`lambda:InvokeFunctionUrl`)
  to call it. There's no public endpoint without this layer in front.

### Why CDK (and not SAM or plain CloudFormation)?

- The Gateway resources (`AWS::BedrockAgentCore::Gateway`,
  `...::GatewayTarget`) already have **stable** support in CloudFormation and
  in the `aws-cdk-lib` L1 constructs (`CfnGateway`, `CfnGatewayTarget`) — no
  custom resources are needed here (unlike the inference-demo, see its
  README).
- SAM is optimized for Lambda + API Gateway; it has no constructs for
  Cognito/CloudFront/AgentCore at the same level of abstraction as CDK.
- CDK in Python keeps the same language as the rest of the project.

## Structure

```
websearch-demo/
  backend/
    handler.py       # Lambda: user-token validation + PKCE proxy + tools/call
  frontend/
    index.html        # Static SPA (plain HTML+JS, no build step): Hosted UI + PKCE
  infra/
    app.py                 # CDK entrypoint
    package.json           # pins the CDK CLI version for 'npx cdk'
    create-admin-user.sh   # creates the default admin user (post-deploy)
    websearch_infra/
      stack.py             # Cognito + Gateway + Target + Lambda + S3 + CloudFront
  .env.example          # copy to .env with your credentials (do NOT commit .env)
```

## Deploy

Prerequisites: Python 3.11+, Node.js (the CDK CLI runs on Node via `jsii`),
Docker (not used here, but `cdk bootstrap` may ask for it), valid AWS
credentials in the `us-east-1` region (the only region with the Web Search
Tool connector available today).

```bash
cp .env.example .env        # fill in your credentials and do NOT commit

# load the AWS credentials into your shell (the .env uses 'export' lines).
# Do this in every new terminal before running cdk:
source .env

cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# install the pinned CDK CLI locally (so 'npx cdk' uses a version
# compatible with aws-cdk-lib, instead of any old global install):
npm install

# sanity check: this should print your AWS account and ARN
aws sts get-caller-identity

# first time in this account/region:
npx cdk bootstrap

npx cdk deploy
```

> If `cdk` reports "Unable to resolve AWS account to use", your credentials
> aren't loaded in the current shell. Run `source .env` (from the repo root)
> again — each new terminal needs it.

> Note: `cdk.json` runs the app with `.venv/bin/python3` explicitly, so the
> CDK CLI always uses the virtualenv's interpreter (where `aws-cdk-lib` is
> installed) regardless of what `python3` your shell resolves to. Just make
> sure you ran `pip install -r requirements.txt` into `infra/.venv`.

At the end, CDK prints the `Outputs`, including `SiteUrl`.

### Create the admin user

Self sign-up is disabled, so create the default admin user once, after the
deploy. From the `infra/` directory:

```bash
./create-admin-user.sh
```

This creates a user with a **permanent** password (no forced reset on first
login). The defaults are:

- email: `admin@example.com`
- password: `Admin123!`

Override them (recommended) by setting env vars before running:

```bash
ADMIN_EMAIL='you@example.com' ADMIN_PASSWORD='ChangeMe!123' ./create-admin-user.sh
```

Then open the `SiteUrl` from the stack outputs and sign in with those
credentials.

## Cleanup

```bash
cd infra
npx cdk destroy
```

This removes all resources (Gateway, Cognito, Lambda, S3, CloudFront). There
are no "shared" resources outside this stack.
