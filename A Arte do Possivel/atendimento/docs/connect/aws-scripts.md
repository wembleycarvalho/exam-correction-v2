---
inclusion: always
---

# AWS Infrastructure Scripts

When creating or modifying AWS resources (Lambda, DynamoDB, Connect, Lex, IAM, AgentCore, etc.):

1. ALWAYS create a Python script file first, never run inline Python via console
2. Write the script to a `.py` file, then execute it with `source .env && python3 <script>.py`
3. This avoids encoding issues, heredoc problems, and makes debugging easier
4. After successful execution, clean up temporary scripts unless the user wants to keep them
5. Always use `source .env` before running scripts that need AWS credentials
6. NEVER re-set (clear + re-set) the WhatsApp event destination via API once it's working. This breaks the Connect integration. Only configure it via the End User Messaging Social console.

# AgentCore Gateway + Connect AI Agent - CRITICAL CONFIG

When creating a Gateway for use with Amazon Connect AI Agent:

1. Gateway auth MUST be CUSTOM_JWT with Discovery URL: `[connect-instance-url]/.well-known/openid-configuration`
2. allowedAudience MUST include the Gateway ID (e.g., `connect-jwt-gateway-4njugyplcw`)
3. Resource-based policy MUST use `"Principal": "*"` (wildcard) because OAuth/JWT auth requires it. Using `"Principal": {"Service": "connect.amazonaws.com"}` will NOT work.
4. The resource policy action should be `bedrock-agentcore:InvokeGateway`
5. The Gateway role must have `lambda:InvokeFunction` permission for the target Lambdas
6. The Gateway must be registered as MCP server integration in Connect console (Integrations > Add integration > MCP server)
7. The AI Agent must have the MCP tools added from the Gateway namespace with "Sufficient" permissions in the Security Profile
8. The AI Agent must be configured in the Connect flow's "Get Customer Input" block with "Habilitar o agente de IA" checked

# Project Maintenance

When making ANY changes to the project (new features, bug fixes, config changes):

1. Update the relevant Lambda code in `lambdas/` if Lambda logic changed
2. Update the relevant setup script in `scripts/` if infrastructure changed
3. Update `docs/ARQUITETURA.md` if architecture or components changed
4. Update `docs/SETUP.md` if setup steps or configuration changed
5. Update `docs/PROMPT.md` if AI Agent prompt or tool instructions changed
6. Update `README.md` if the change affects the project overview, structure, or usage
7. Update `.env.example` if new environment variables were introduced
8. Update `scripts/env_helper.py` sections if new env var categories were added
9. If a new resource is created by a setup script, use `set_env()` to propagate its ID/ARN to `.env`
