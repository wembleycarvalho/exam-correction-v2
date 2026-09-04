/**
 * Atendimento — ponte de STREAMING (Lambda Node.js, response streaming).
 *
 * O browser não fala direto com o AgentCore Runtime (precisa de IAM). Esta Lambda:
 *   1. valida o JWT do Cognito do portal (Authorization: Bearer, ou X-Cognito-Token),
 *   2. chama InvokeAgentRuntime (streaming) no agente `atendimento_assistant`,
 *   3. repassa os chunks como SSE (text/event-stream) ao browser, token-a-token.
 *
 * O AgentCore Runtime já emite frames SSE `data: "<delta>"\n\n` (o entrypoint faz yield dos
 * deltas); então a ponte basicamente ENCAMINHA os bytes. Function URL em RESPONSE_STREAM,
 * atrás do CloudFront (behavior /atendimento/api/ask, sem cache).
 *
 * Sem dependências além do AWS SDK v3 (client-bedrock-agentcore). JWT verificado com o
 * `crypto` nativo do Node (JWK -> chave pública -> RS256), sem libs externas.
 */
import crypto from "node:crypto";
import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from "@aws-sdk/client-bedrock-agentcore";
import { SSMClient, GetParameterCommand } from "@aws-sdk/client-ssm";

const REGION = process.env.AWS_REGION || "us-east-1";
const POOL_ID = process.env.POOL_ID || "";
const ISSUER = `https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}`;
const REQUIRE_AUTH = (process.env.REQUIRE_AUTH || "true").toLowerCase() !== "false";

const ac = new BedrockAgentCoreClient({ region: REGION });
const ssm = new SSMClient({ region: REGION });

let _runtimeArn = process.env.RUNTIME_ARN || "";
let _jwks = null;

async function runtimeArn() {
  if (_runtimeArn) return _runtimeArn;
  const r = await ssm.send(new GetParameterCommand({ Name: "/atendimento/runtime-arn" }));
  _runtimeArn = r.Parameter.Value;
  return _runtimeArn;
}

async function jwks() {
  if (_jwks) return _jwks;
  const res = await fetch(`${ISSUER}/.well-known/jwks.json`);
  _jwks = (await res.json()).keys;
  return _jwks;
}

function b64urlToJson(s) {
  return JSON.parse(Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8"));
}

async function verifyJwt(token) {
  if (!REQUIRE_AUTH) return {};
  if (!token) throw new Error("missing token");
  const [h, p, sig] = token.split(".");
  if (!h || !p || !sig) throw new Error("malformed token");
  const header = b64urlToJson(h);
  const keys = await jwks();
  const jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) throw new Error("unknown kid");
  const pub = crypto.createPublicKey({ key: jwk, format: "jwk" });
  const ok = crypto.verify(
    "RSA-SHA256",
    Buffer.from(`${h}.${p}`),
    pub,
    Buffer.from(sig.replace(/-/g, "+").replace(/_/g, "/"), "base64")
  );
  if (!ok) throw new Error("bad signature");
  const claims = b64urlToJson(p);
  if (claims.iss !== ISSUER) throw new Error("bad issuer");
  if (claims.exp && Date.now() / 1000 > claims.exp) throw new Error("expired");
  if (claims.token_use && !["access", "id"].includes(claims.token_use)) throw new Error("bad token_use");
  return claims;
}

function sessionId(sub, conv) {
  // AgentCore exige runtimeSessionId com >= 33 caracteres.
  return crypto.createHash("sha256").update(`atend:${sub || ""}:${conv || ""}`).digest("hex");
}

function sse(obj) {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

export const handler = awslambda.streamifyResponse(async (event, responseStream, _context) => {
  const meta = {
    statusCode: 200,
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform",
               "X-Accel-Buffering": "no" },
  };
  const out = awslambda.HttpResponseStream.from(responseStream, meta);
  try {
    const headers = event.headers || {};
    const auth = headers.authorization || headers.Authorization || "";
    const bearer = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : "";
    const token = headers["x-cognito-token"] || headers["X-Cognito-Token"] || bearer;
    const claims = await verifyJwt(token);

    const body = event.body
      ? JSON.parse(event.isBase64Encoded ? Buffer.from(event.body, "base64").toString("utf8") : event.body)
      : {};
    const question = (body.question || body.prompt || "").trim();
    if (!question) { out.write(sse({ type: "error", error: "pergunta vazia" })); out.end(); return; }

    const arn = await runtimeArn();
    const resp = await ac.send(new InvokeAgentRuntimeCommand({
      agentRuntimeArn: arn,
      runtimeSessionId: sessionId(claims.sub, body.conv),
      contentType: "application/json",
      accept: "text/event-stream",
      payload: Buffer.from(JSON.stringify({
        question, history: body.history || [], system_prompt: body.system_prompt || "",
      })),
    }));
    // resp.response é um stream (async iterable de Uint8Array). O Runtime já formata SSE
    // (data: "<delta>"), então encaminhamos os bytes direto ao browser.
    const stream = resp.response;
    if (stream && typeof stream[Symbol.asyncIterator] === "function") {
      for await (const chunk of stream) {
        out.write(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
      }
    } else if (stream && typeof stream.transformToString === "function") {
      out.write(await stream.transformToString());
    }
    out.write(sse({ type: "done" }));
    out.end();
  } catch (e) {
    const code = /token|issuer|signature|expired|kid/i.test(String(e && e.message)) ? "401" : "502";
    try { out.write(sse({ type: "error", error: String((e && e.message) || e), code })); } catch (_) {}
    out.end();
  }
});
