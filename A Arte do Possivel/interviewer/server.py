import asyncio
import base64
import json
import random
import uuid
import os
from datetime import datetime
from decimal import Decimal

# Load .env file (supports 'export KEY=VAL' format)
def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export ")
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response

from aws_sdk_bedrock_runtime.client import (
    BedrockRuntimeClient,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from aws_sdk_bedrock_runtime.models import (
    InvokeModelWithBidirectionalStreamInputChunk,
    BidirectionalInputPayloadPart,
)
from aws_sdk_bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from smithy_aws_core.identity import EnvironmentCredentialsResolver

import boto3

app = FastAPI()

# Servido sob /entrevistador (mesma origem do portal, via CloudFront → ALB → Fargate).
BASE = os.environ.get("BASE_PATH", "/entrevistador")
app.mount(f"{BASE}/static", StaticFiles(directory="static"), name="static")

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-2-sonic-v1:0")
VOICE_ID = os.environ.get("VOICE_ID", "carolina")
# Vozes pt-BR do Nova 2 Sonic: feminina=carolina, masculina=leo (configuráveis por env).
VOICE_ID_FEMALE = os.environ.get("VOICE_ID_FEMALE", "carolina")
VOICE_ID_MALE = os.environ.get("VOICE_ID_MALE", "leo")
VAGAS_TABLE = os.environ.get("VAGAS_TABLE", "")
REPORTS_TABLE = os.environ.get("REPORTS_TABLE", "")
AVATARS_TABLE = os.environ.get("AVATARS_TABLE", "")
AVATARS_BUCKET = os.environ.get("AVATARS_BUCKET", "")
IMAGE_MODEL_ID = os.environ.get("IMAGE_MODEL_ID", "stability.stable-image-ultra-v1:1")
IMAGE_MODEL_REGION = os.environ.get("IMAGE_MODEL_REGION", "us-west-2")

INTERVIEWER_PROMPT_TEMPLATE = """You are a professional job interviewer named {interviewer_name} conducting a quick interview simulation \
of 3 to 5 minutes. You and the candidate will engage in a spoken dialog in real time.

#1 HIGHEST PRIORITY RULE — CANDIDATE QUESTIONS:
Every time the candidate says ANYTHING that contains a question — whether it is a direct question, a doubt, a request \
for clarification, or a question embedded inside their answer — you MUST:
  Step 1: Briefly acknowledge their answer (one sentence).
  Step 2: Answer their question completely and helpfully.
  Step 3: Only AFTER answering, ask your next interview question.
You are FORBIDDEN from skipping, ignoring, or postponing a candidate's question. \
If you detect any interrogative intent (words like "qual", "como", "quanto", "onde", "quando", "por que", "será que", \
"vocês", "a empresa", "o time", "?"), you MUST treat it as a question and answer it.

OTHER RULES:
- Ask only ONE short question at a time (max 15 words), then STOP and WAIT.
- NEVER combine two questions in the same turn.
- Be completely silent after asking and wait for the full response.

IMPORTANT: You MUST speak first. Greet the candidate warmly as soon as the session starts.

LANGUAGE: Always speak in Brazilian Portuguese (pt-BR).

Interview flow:
1. Greet warmly: "Olá, tudo bem? Eu sou {article} {interviewer_name}, vou conduzir a sua entrevista hoje para a vaga de [position name]. Que bom ter você aqui! Para começar, me conta um pouquinho sobre você — seu nome, sua formação e o que você faz atualmente." WAIT.
2. Ask first question (relevant experience). WAIT.
3. Ask second question (behavioral/situational). WAIT.
4. Ask third question (technical/role-specific). WAIT.
5. Optionally one quick question (motivation). WAIT.
6. Ask: "Você tem alguma dúvida ou pergunta sobre a vaga ou a empresa?" WAIT.
7. If they have questions, answer fully. Ask if they have more. Repeat until no more questions.
8. Only when they have no more questions, thank them by name and say goodbye.
9. Your VERY LAST message must end with: [ENTREVISTA FINALIZADA]

Style:
- Short, direct questions. Example: "Qual sua experiência com fermentação natural?"
- Brief transitions: "Ótimo, obrigada." or "Entendi."
- No long feedback between questions.
- 3 to 4 questions total, plus Q&A at the end.
- NEVER say "Aguardo sua resposta", "Pode responder", "Estou ouvindo" or any variation. Just ask the question and stop talking. The silence IS the wait.

JOB DESCRIPTION:
{job_description}
"""

REPORT_PROMPT_TEMPLATE = """You are an expert HR analyst. Based on the interview transcript below for the given job position, \
generate a structured evaluation report in Brazilian Portuguese (pt-BR).

Use the candidate's self-introduction (name, background, current role) from the beginning of the interview to personalize the report.

IMPORTANT: You MUST respond using EXACTLY the template below. Do not change the section headers, do not reorder, do not skip sections. \
Fill in the content for each section based on the interview. The first line MUST be the score.

TEMPLATE (copy this structure exactly):

SCORE:<number 0-100>
CANDIDATE:<candidate's full name exactly as stated in the self-introduction; if the candidate did not state a name, write "Não informado">

**Candidato(a):** <name and brief profile from self-introduction>

**Vaga:** <position title>

**Resumo:** <2-3 sentences about overall performance>

**Pontos Fortes:**
- <strong point 1>
- <strong point 2>
- <strong point 3>

**Pontos Fracos / Áreas de Melhoria:**
- <weakness 1>
- <weakness 2>
- <weakness 3>

**Competências Avaliadas:**
- Conhecimento Técnico/Função: <⭐ to ⭐⭐⭐⭐⭐>
- Comunicação: <⭐ to ⭐⭐⭐⭐⭐>
- Resolução de Problemas: <⭐ to ⭐⭐⭐⭐⭐>
- Fit Cultural / Motivação: <⭐ to ⭐⭐⭐⭐⭐>
- Experiência Relevante: <⭐ to ⭐⭐⭐⭐⭐>

**Recomendação:** <FORTEMENTE RECOMENDADO | RECOMENDADO | RECOMENDADO COM RESSALVAS | NÃO RECOMENDADO>

**Comportamento na Entrevista:**
- Interrupções ao entrevistador: <count interruptions marked as [Candidato interrompeu o entrevistador] in transcript. Assess if frequent (negative) or none (positive)>
- Vícios de linguagem: <identify repeated filler words like "tipo", "né", "então", "assim", "basicamente", "na verdade", "acho que", "hmm". List them with approximate frequency. If none, note positively>
- Clareza e objetividade: <were answers direct and well-structured, or rambling and unfocused? Did the candidate use structured reasoning like STAR method?>
- Confiança: <did the candidate sound confident or hesitant? Look for hedging language like "talvez", "acho que", "não sei se", excessive "hmm/ahh">
- Tempo de resposta: <were answers too short (possible disinterest) or too long (lack of synthesis)? Balanced?>
- Engajamento: <did the candidate show genuine interest? Asked questions? Showed enthusiasm? Or just answered minimally?>
- Coerência: <did the candidate contradict themselves at any point during the interview?>
- Vocabulário: <was the language register appropriate for the role level? Too informal? Too technical? Well-matched?>

**Observações Adicionais:** <any other relevant observations>

END OF TEMPLATE.

JOB DESCRIPTION:
{job_description}

INTERVIEW TRANSCRIPT:
{transcript}
"""

INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000
class InterviewRecorder:
    """Persiste transcrição + relatório de cada entrevista no DynamoDB (ReportsTable).

    Antes gravava arquivos (txt/html/json) no disco do container — armazenamento efêmero
    que era apagado a cada deploy. Agora tudo vai para o DynamoDB (RETAIN)."""

    def __init__(self, session_id: str, job_description: str):
        self.session_id = session_id
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.job_description = job_description

    def add_input_audio(self, b64_audio: str):
        pass

    def add_output_audio(self, b64_audio: str):
        pass

    def save(self, transcript: list, report: str, token_usage: dict):
        """Grava o relatório no DynamoDB. Roda em thread (boto3 é blocking)."""
        if not _reports_table:
            print("REPORTS_TABLE não configurada — relatório não persistido")
            return
        score, candidate, body = parse_report_meta(report)
        ts_display = datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M")
        item = {
            "reportId": f"{self.timestamp}_{self.session_id[:8]}",
            "createdAt": datetime.now().isoformat(),
            "timestamp": self.timestamp,
            "timestampDisplay": ts_display,
            "jobDescription": self.job_description,
            "candidateName": candidate or "Não informado",
            "score": score if score is not None else -1,
            "reportBody": body,
            "transcript": transcript or [],
            "tokenUsage": {k: int(v) for k, v in (token_usage or {}).items()},
        }
        try:
            _reports_table.put_item(Item=item)
            print(f"Interview persisted: {item['reportId']}")
        except Exception as e:
            print(f"Erro ao persistir relatório: {e}")


def parse_report_meta(report: str):
    """Extrai (score, candidate_name, corpo) das linhas-marcador SCORE:/CANDIDATE:.

    Essas linhas são só para máquina e são removidas do corpo exibido; o corpo mantém a
    seção humana **Candidato(a):** gerada pelo modelo."""
    import re
    score = None
    candidate = ""
    body = report or ""
    m = re.search(r"SCORE:\s*(\d+)", body, re.IGNORECASE)
    if m:
        score = int(m.group(1))
        body = re.sub(r"SCORE:\s*\d+%?\s*", "", body, count=1, flags=re.IGNORECASE)
    mc = re.search(r"CANDIDATE:\s*(.+)", body, re.IGNORECASE)
    if mc:
        candidate = mc.group(1).strip()
        body = re.sub(r"CANDIDATE:.*(\n|$)", "", body, count=1, flags=re.IGNORECASE)
    return score, candidate, body.strip()


def render_report_html(*, job_description: str, ts_display: str, report_body: str,
                       score, transcript: list, token_usage: dict) -> str:
    """Renderiza o HTML do relatório a partir dos dados persistidos (sem tocar em disco)."""
    import re

    # Semáforo
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = -1
    if score < 0:
        color, light_class, label = "#888", "none", "N/A"
        score = 0
    elif score >= 70:
        color, light_class, label = "#4caf50", "green", "Alta aderência"
    elif score >= 40:
        color, light_class, label = "#ffc107", "yellow", "Aderência parcial"
    else:
        color, light_class, label = "#f44336", "red", "Baixa aderência"

    # Markdown-ish to HTML
    body_html = report_body or ""
    body_html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body_html)
    body_html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", body_html, flags=re.MULTILINE)
    body_html = re.sub(r"^## (.+)$", r"<h3>\1</h3>", body_html, flags=re.MULTILINE)
    body_html = re.sub(r"^- (.+)$", r"<li>\1</li>", body_html, flags=re.MULTILINE)
    body_html = body_html.replace("\n", "<br>")

    # Transcript HTML
    transcript_html = ""
    for entry in (transcript or []):
        role = entry.get("role", "")
        text = entry.get("text", "")
        if role == "Candidato":
            transcript_html += f'<div class="msg-user">🧑 {role}: {text}</div>'
        elif role == "Entrevistador":
            transcript_html += f'<div class="msg-assistant">🎙️ {role}: {text}</div>'
        else:
            transcript_html += f'<div class="msg-system">ℹ️ {role}: {text}</div>'

    # Token cost
    cost_html = ""
    tu = {k: int(v) for k, v in (token_usage or {}).items()}
    if tu.get("total", 0) > 0:
        in_s = tu.get("input_speech", 0)
        in_t = tu.get("input_text", 0)
        out_s = tu.get("output_speech", 0)
        out_t = tu.get("output_text", 0)
        total = tu.get("total", 0)
        cost = (in_s + in_t) / 1000 * 0.0034 + (out_s + out_t) / 1000 * 0.0136
        cost_html = f"""
        <div class="token-panel">
            <div class="token-title">💰 Consumo de Tokens & Custo</div>
            <table>
                <tr><td>🎤 Input Speech</td><td>{in_s:,}</td></tr>
                <tr><td>📝 Input Text</td><td>{in_t:,}</td></tr>
                <tr><td>🔊 Output Speech</td><td>{out_s:,}</td></tr>
                <tr><td>💬 Output Text</td><td>{out_t:,}</td></tr>
                <tr><td>📊 Total</td><td>{total:,}</td></tr>
                <tr class="cost-row"><td>💵 Custo estimado</td><td>US$ {cost:.4f}</td></tr>
            </table>
        </div>"""

    # No audio player
    audio_html = ""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório de Entrevista — {ts_display}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#0f0f1a; color:#e0e0e0; padding:2rem; max-width:800px; margin:0 auto; }}
h1 {{ font-size:1.4rem; color:#8b9cf7; margin-bottom:0.3rem; }}
.subtitle {{ font-size:0.85rem; color:#666; margin-bottom:1.5rem; }}
.score-panel {{ display:flex; align-items:center; gap:1.2rem; padding:1rem 1.2rem; border-radius:10px; margin-bottom:1.2rem; background:#12122a; }}
.semaforo {{ display:flex; flex-direction:column; gap:6px; padding:8px; background:#222; border-radius:8px; }}
.light {{ width:28px; height:28px; border-radius:50%; background:#333; }}
.light.on {{ background:{color}; box-shadow:0 0 12px {color}; }}
.score-value {{ font-size:2rem; font-weight:700; color:{color}; }}
.score-label {{ font-size:0.85rem; color:#aaa; }}
.score-bar-bg {{ width:200px; height:10px; background:#333; border-radius:5px; overflow:hidden; margin-top:4px; }}
.score-bar {{ height:100%; width:{score}%; background:{color}; border-radius:5px; }}
.report {{ padding:1.5rem; background:#1a1a2e; border-radius:12px; font-size:0.85rem; line-height:1.7; margin-bottom:1.5rem; }}
.report strong {{ color:#a5d6a7; }}
.report h3 {{ color:#8b9cf7; margin-top:1rem; }}
.report li {{ margin-left:1rem; list-style:none; }}
.report li::before {{ content:"• "; }}
.audio-player {{ padding:1rem; background:#12122a; border-radius:10px; margin-bottom:1.5rem; }}
.audio-title {{ font-size:0.9rem; color:#8b9cf7; font-weight:600; margin-bottom:0.5rem; }}
.transcript {{ padding:1rem; background:#1a1a2e; border-radius:12px; font-size:0.85rem; line-height:1.6; margin-bottom:1.5rem; max-height:400px; overflow-y:auto; }}
.msg-user {{ color:#6ec6ff; margin-bottom:0.5rem; }}
.msg-assistant {{ color:#a5d6a7; margin-bottom:0.5rem; }}
.msg-system {{ color:#888; font-style:italic; margin-bottom:0.5rem; }}
.token-panel {{ padding:0.8rem 1rem; background:#12122a; border-radius:8px; font-size:0.8rem; color:#aaa; margin-bottom:1.5rem; }}
.token-title {{ color:#8b9cf7; font-weight:600; margin-bottom:0.5rem; }}
.token-panel table {{ width:100%; border-collapse:collapse; }}
.token-panel td {{ padding:0.2rem 0.5rem; }}
.token-panel td:last-child {{ text-align:right; color:#e0e0e0; }}
.cost-row td {{ border-top:1px solid #333; padding-top:0.4rem; color:#ffc107; font-weight:600; }}
.section-title {{ font-size:1rem; color:#8b9cf7; margin:1.5rem 0 0.5rem; }}
</style>
</head>
<body>
<h1>📋 Relatório de Entrevista</h1>
<p class="subtitle">{ts_display} — {job_description[:100]}</p>

<div class="score-panel">
  <div class="semaforo">
    <div class="light {"on" if light_class == "green" else ""}"></div>
    <div class="light {"on" if light_class == "yellow" else ""}"></div>
    <div class="light {"on" if light_class == "red" else ""}"></div>
  </div>
  <div>
    <div class="score-value">{score}%</div>
    <div class="score-label">{label}</div>
    <div class="score-bar-bg"><div class="score-bar"></div></div>
  </div>
</div>

{audio_html}

<div class="report">{body_html}</div>

<div class="section-title">💬 Transcrição</div>
<div class="transcript">{transcript_html}</div>

{cost_html}

</body>
</html>"""
    return html



# Sessão boto3 única, criada na importação — ANTES de qualquer AWS_* ser escrito no
# ambiente. Assim a cadeia de credenciais resolve para a role da task ECS (endpoint de
# credenciais do container), que devolve RefreshableCredentials e se renova sozinha.
# Se criássemos uma boto3.Session() nova a cada sessão, depois de _refresh_env_credentials
# ter escrito AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN no ambiente, o provider de variáveis
# de ambiente (prioridade máxima) devolveria aquele snapshot ESTÁTICO já congelado — que
# expira e nunca renova → InvokeModelWithBidirectionalStream 403 ExpiredTokenException.
_CRED_SESSION = boto3.Session()
try:
    # Força a resolução da cadeia AGORA (trava o provider da role/container, refreshable).
    _CRED_SESSION.get_credentials()
except Exception as e:  # noqa: BLE001
    print(f"[creds] resolução inicial falhou: {e}")


def _refresh_env_credentials():
    """Repõe AWS_* no ambiente a partir da sessão boto3 fixa (role da task ECS), que se
    renova sozinha. Chamado a cada nova sessão, pois o cliente bidirecional usa
    EnvironmentCredentialsResolver (lê AWS_* do env). get_frozen_credentials() dispara o
    refresh quando as credenciais estão perto de expirar, evitando ExpiredTokenException."""
    try:
        creds = _CRED_SESSION.get_credentials()
        if creds:
            fz = creds.get_frozen_credentials()
            os.environ["AWS_ACCESS_KEY_ID"] = fz.access_key
            os.environ["AWS_SECRET_ACCESS_KEY"] = fz.secret_key
            if fz.token:
                os.environ["AWS_SESSION_TOKEN"] = fz.token
            else:
                os.environ.pop("AWS_SESSION_TOKEN", None)
    except Exception as e:  # noqa: BLE001
        print(f"[creds] refresh falhou: {e}")


def create_bedrock_client():
    _refresh_env_credentials()
    config = Config(
        endpoint_uri=f"https://bedrock-runtime.{REGION}.amazonaws.com",
        region=REGION,
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        auth_scheme_resolver=HTTPAuthSchemeResolver(),
        auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")},
    )
    return BedrockRuntimeClient(config=config)


class NovaSonicSession:
    def __init__(self, job_description: str, interviewer_name: str = "Carolina", gender: str = "female"):
        self.client = create_bedrock_client()
        self.prompt_name = str(uuid.uuid4())
        self.content_name = str(uuid.uuid4())
        self.audio_content_name = str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())
        self.stream = None
        self.is_active = False
        self.job_description = job_description
        self.transcript = []
        self.current_role = ""
        self.interviewer_name = interviewer_name or "Carolina"
        g = (gender or "female").lower()
        self.voice_id = VOICE_ID_MALE if g == "male" else VOICE_ID_FEMALE
        self.system_prompt = INTERVIEWER_PROMPT_TEMPLATE.format(
            job_description=job_description,
            interviewer_name=self.interviewer_name,
            article=("o" if g == "male" else "a"),
        )
        self.token_usage = {
            "input_speech": 0, "input_text": 0,
            "output_speech": 0, "output_text": 0,
            "total_input": 0, "total_output": 0, "total": 0,
        }
        self.recorder = InterviewRecorder(self.session_id, job_description)
        self.interruption_count = 0

    async def send_event(self, event_dict):
        payload = json.dumps(event_dict)
        event = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(bytes_=payload.encode("utf-8"))
        )
        await self.stream.input_stream.send(event)

    async def send_setup_events(self):
        """Send all setup events after stream is already open."""

        # 1. Session start
        await self.send_event({
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": 1024,
                        "topP": 0.9,
                        "temperature": 0.7,
                    },
                    "turnDetectionConfiguration": {
                        "endpointingSensitivity": "MEDIUM"
                    },
                }
            }
        })

        # 2. Prompt start
        await self.send_event({
            "event": {
                "promptStart": {
                    "promptName": self.prompt_name,
                    "textOutputConfiguration": {"mediaType": "text/plain"},
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": OUTPUT_SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "voiceId": self.voice_id,
                        "encoding": "base64",
                        "audioType": "SPEECH",
                    },
                }
            }
        })

        # 3. System prompt
        await self.send_event({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": self.content_name,
                    "type": "TEXT",
                    "interactive": True,
                    "role": "SYSTEM",
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        })
        await self.send_event({
            "event": {
                "textInput": {
                    "promptName": self.prompt_name,
                    "contentName": self.content_name,
                    "content": self.system_prompt,
                }
            }
        })
        await self.send_event({
            "event": {
                "contentEnd": {
                    "promptName": self.prompt_name,
                    "contentName": self.content_name,
                }
            }
        })

        # 4. Send a user text nudge to make the model speak first (cross-modal input)
        nudge_content_name = str(uuid.uuid4())
        await self.send_event({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": nudge_content_name,
                    "type": "TEXT",
                    "interactive": True,
                    "role": "USER",
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        })
        await self.send_event({
            "event": {
                "textInput": {
                    "promptName": self.prompt_name,
                    "contentName": nudge_content_name,
                    "content": "Olá, estou pronto para a entrevista. Por favor, se apresente e comece.",
                }
            }
        })
        await self.send_event({
            "event": {
                "contentEnd": {
                    "promptName": self.prompt_name,
                    "contentName": nudge_content_name,
                }
            }
        })

        # 5. Audio content start (stays open for continuous streaming)
        await self.send_event({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": INPUT_SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                        "audioType": "SPEECH",
                        "encoding": "base64",
                    },
                }
            }
        })

    async def send_audio(self, base64_audio: str):
        if not self.is_active:
            return
        await self.send_event({
            "event": {
                "audioInput": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
                    "content": base64_audio,
                }
            }
        })

    async def stop(self):
        if not self.is_active:
            return
        self.is_active = False
        try:
            await self.send_event({
                "event": {
                    "contentEnd": {
                        "promptName": self.prompt_name,
                        "contentName": self.audio_content_name,
                    }
                }
            })
            await self.send_event({
                "event": {"promptEnd": {"promptName": self.prompt_name}}
            })
            await self.send_event({"event": {"sessionEnd": {}}})
            await self.stream.input_stream.close()
        except Exception as e:
            print(f"Error stopping session: {e}")


def generate_report_sync(job_description: str, transcript: list) -> str:
    """Generate evaluation report using Bedrock Nova Lite via boto3 (blocking)."""
    transcript_text = "\n".join(
        f"{entry['role']}: {entry['text']}" for entry in transcript
    )
    prompt = REPORT_PROMPT_TEMPLATE.format(
        job_description=job_description,
        transcript=transcript_text,
    )

    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    response = bedrock.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0.3},
        }),
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


@app.get(BASE + "/health")
async def health():
    return {"status": "ok"}


@app.get(BASE)
@app.get(BASE + "/")
async def index():
    return FileResponse("static/index.html")


@app.get(BASE + "/api/reports")
async def list_reports():
    """Lista o histórico de entrevistas a partir do DynamoDB (persistente)."""
    if not _reports_table:
        return {"reports": []}
    items = await asyncio.to_thread(lambda: _reports_table.scan().get("Items", []))
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    reports = []
    for it in items:
        try:
            score = int(it.get("score", -1))
        except (TypeError, ValueError):
            score = -1
        reports.append({
            "id": it["reportId"],
            "timestamp": it.get("timestamp", ""),
            "candidateName": it.get("candidateName", "Não informado"),
            "score": score,
            "job_description": (it.get("jobDescription", "") or "")[:120],
            "token_usage": {k: int(v) for k, v in (it.get("tokenUsage", {}) or {}).items()},
            "html_url": f"{BASE}/api/reports/{it['reportId']}/html",
        })
    return {"reports": reports}


@app.get(BASE + "/api/reports/{report_id}")
async def get_report(report_id: str):
    """Retorna os dados de um relatório (JSON) para exibição inline no portal."""
    if not _reports_table:
        return {"error": "tabela de relatórios não configurada"}
    item = await asyncio.to_thread(
        lambda: _reports_table.get_item(Key={"reportId": report_id}).get("Item"))
    if not item:
        return {"error": "não encontrado"}
    try:
        score = int(item.get("score", -1))
    except (TypeError, ValueError):
        score = -1
    return {
        "id": item["reportId"],
        "candidateName": item.get("candidateName", "Não informado"),
        "jobDescription": item.get("jobDescription", ""),
        "timestampDisplay": item.get("timestampDisplay", ""),
        "score": score,
        "reportBody": item.get("reportBody", ""),
        "transcript": item.get("transcript", []),
        "tokenUsage": {k: int(v) for k, v in (item.get("tokenUsage", {}) or {}).items()},
    }


@app.get(BASE + "/api/reports/{report_id}/html", response_class=HTMLResponse)
async def report_html(report_id: str):
    """Renderiza o relatório completo em HTML a partir dos dados no DynamoDB."""
    if not _reports_table:
        return HTMLResponse("<h1>Tabela de relatórios não configurada</h1>", status_code=500)
    item = await asyncio.to_thread(
        lambda: _reports_table.get_item(Key={"reportId": report_id}).get("Item"))
    if not item:
        return HTMLResponse("<h1>Relatório não encontrado</h1>", status_code=404)
    html = render_report_html(
        job_description=item.get("jobDescription", ""),
        ts_display=item.get("timestampDisplay", ""),
        report_body=item.get("reportBody", ""),
        score=item.get("score", -1),
        transcript=item.get("transcript", []),
        token_usage=item.get("tokenUsage", {}),
    )
    return HTMLResponse(html)


@app.delete(BASE + "/api/reports/{report_id}")
async def delete_report(report_id: str):
    """Exclui uma entrevista do histórico (DynamoDB)."""
    if not _reports_table:
        return {"error": "tabela de relatórios não configurada"}
    await asyncio.to_thread(lambda: _reports_table.delete_item(Key={"reportId": report_id}))
    return {"deleted": report_id}


from pydantic import BaseModel

class GenerateJobRequest(BaseModel):
    input: str

@app.post(BASE + "/api/generate-job")
async def generate_job_description(req: GenerateJobRequest):
    """Generate a full job description from a brief input using Nova Lite."""
    def _generate():
        prompt = f"""Você é um especialista em recrutamento e seleção. Com base na entrada abaixo, gere uma descrição de vaga \
completa e profissional em português brasileiro.

A descrição deve incluir:
- Título da vaga e nome fictício de empresa
- Localização
- Responsabilidades (6-10 itens)
- Requisitos (6-8 itens)
- Diferenciais (3-4 itens)
- O que oferecemos (4-6 itens com faixa salarial realista)

Se a entrada for apenas um cargo (ex: "padeiro"), crie uma descrição completa e realista para esse cargo.
Se a entrada for uma descrição parcial, complete e enriqueça mantendo o que foi fornecido.

Retorne APENAS o texto da descrição, sem markdown, sem explicações adicionais.

ENTRADA DO USUÁRIO:
{req.input}"""

        bedrock = boto3.client("bedrock-runtime", region_name=REGION)
        response = bedrock.invoke_model(
            modelId="amazon.nova-lite-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 2048, "temperature": 0.7},
            }),
        )
        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]

    description = await asyncio.to_thread(_generate)
    return {"description": description}


# ---------------- Vagas (DynamoDB) ----------------
_vagas_table = boto3.resource("dynamodb", region_name=REGION).Table(VAGAS_TABLE) if VAGAS_TABLE else None
_reports_table = boto3.resource("dynamodb", region_name=REGION).Table(REPORTS_TABLE) if REPORTS_TABLE else None
_avatars_table = boto3.resource("dynamodb", region_name=REGION).Table(AVATARS_TABLE) if AVATARS_TABLE else None
_s3 = boto3.client("s3", region_name=REGION)
_bedrock_img = boto3.client("bedrock-runtime", region_name=IMAGE_MODEL_REGION)

# Calibração padrão (posições de olhos/boca sobre a foto 400x400) — igual ao default do avatar.js.
DEFAULT_FACE = {
    "leftEye": {"x": 146, "y": 192, "w": 16, "h": 6},
    "rightEye": {"x": 253, "y": 194, "w": 16, "h": 6},
    "mouth": {"x": 200, "y": 297, "w": 39, "h": 8},
    "mouthOpenMax": 6, "mouthSplitH": 8,
}


def _to_decimal(o):
    """boto3 resource não aceita float — converte floats para Decimal recursivamente."""
    if isinstance(o, float):
        return Decimal(str(o))
    if isinstance(o, list):
        return [_to_decimal(x) for x in o]
    if isinstance(o, dict):
        return {k: _to_decimal(v) for k, v in o.items()}
    return o


def _deep_num(o):
    """Converte Decimals do DynamoDB de volta para int/float (JSON-serializável)."""
    if isinstance(o, list):
        return [_deep_num(x) for x in o]
    if isinstance(o, dict):
        return {k: _deep_num(v) for k, v in o.items()}
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    return o


def _seed_vagas():
    """Semeia a tabela com as vagas iniciais (static/jobs.json) se estiver vazia."""
    if not _vagas_table:
        return
    try:
        if _vagas_table.scan(Select="COUNT").get("Count", 0):
            return
        with open("static/jobs.json", encoding="utf-8") as f:
            seed = json.load(f)
        for j in seed:
            _vagas_table.put_item(Item={
                "vagaId": j.get("id") or ("v" + uuid.uuid4().hex[:12]),
                "title": j["title"], "description": j["description"],
                "createdAt": datetime.now().isoformat(),
            })
        print(f"[vagas] semeadas {len(seed)} vagas iniciais")
    except Exception as e:  # noqa: BLE001
        print(f"[vagas] seed falhou: {e}")


def _seed_avatars():
    """Cria o avatar inicial (Carolina) se a tabela estiver vazia, subindo a foto embutida
    no container (static/carolina_photo.jpg) para o S3 privado de avatares."""
    if not _avatars_table or not AVATARS_BUCKET:
        return
    try:
        if _avatars_table.scan(Select="COUNT").get("Count", 0):
            return
        avatar_id = "a" + uuid.uuid4().hex[:12]
        key = f"avatars/{avatar_id}.jpg"
        with open("static/carolina_photo.jpg", "rb") as f:
            _s3.put_object(Bucket=AVATARS_BUCKET, Key=key, Body=f.read(), ContentType="image/jpeg")
        _avatars_table.put_item(Item={
            "avatarId": avatar_id, "name": "Carolina", "imageKey": key,
            "contentType": "image/jpeg", "calibration": _to_decimal(DEFAULT_FACE),
            "gender": "female", "isDefault": True, "createdAt": datetime.now().isoformat(),
        })
        print(f"[avatars] avatar inicial semeado: {avatar_id}")
    except Exception as e:  # noqa: BLE001
        print(f"[avatars] seed falhou: {e}")


@app.on_event("startup")
async def _startup_seed():
    await asyncio.to_thread(_seed_vagas)
    await asyncio.to_thread(_seed_avatars)


# ---------------- Avatares (DynamoDB + S3 privado) ----------------
class AvatarUpload(BaseModel):
    name: str
    imageBase64: str
    contentType: str = "image/png"


class AvatarGenerate(BaseModel):
    name: str
    prompt: str = ""
    style: str = "desenho"


class AvatarUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    calibration: dict | None = None


def _avatar_public(i: dict) -> dict:
    return {
        "id": i["avatarId"],
        "name": i.get("name", ""),
        "gender": i.get("gender", "female"),
        "isDefault": bool(i.get("isDefault", False)),
        "imageUrl": f"{BASE}/api/avatars/{i['avatarId']}/image",
        "calibration": _deep_num(i.get("calibration", {})),
    }


def _default_avatar_meta():
    """(nome, gênero) do avatar padrão — usado na entrevista (voz + nome no prompt).
    Fallback Carolina/female."""
    if not _avatars_table:
        return ("Carolina", "female")
    try:
        items = _avatars_table.scan().get("Items", [])
        if not items:
            return ("Carolina", "female")
        items.sort(key=lambda x: (not bool(x.get("isDefault", False)), x.get("createdAt", "")))
        a = items[0]
        return (a.get("name") or "Carolina", (a.get("gender") or "female").lower())
    except Exception:
        return ("Carolina", "female")


@app.get(BASE + "/api/avatars")
async def list_avatars():
    if not _avatars_table:
        return {"avatars": []}
    items = await asyncio.to_thread(lambda: _avatars_table.scan().get("Items", []))
    # Padrão primeiro, depois por data de criação.
    items.sort(key=lambda x: (not bool(x.get("isDefault", False)), x.get("createdAt", "")))
    return {"avatars": [_avatar_public(i) for i in items]}


@app.get(BASE + "/api/avatars/default")
async def default_avatar():
    """Avatar padrão (usado pela entrevista): imagem + calibração."""
    if not _avatars_table:
        return {"error": "avatars não configurado"}
    items = await asyncio.to_thread(lambda: _avatars_table.scan().get("Items", []))
    if not items:
        return {"error": "nenhum avatar"}
    items.sort(key=lambda x: (not bool(x.get("isDefault", False)), x.get("createdAt", "")))
    return _avatar_public(items[0])


@app.get(BASE + "/api/avatars/{avatar_id}/image")
async def avatar_image(avatar_id: str):
    if not _avatars_table:
        return Response(status_code=404)
    item = await asyncio.to_thread(
        lambda: _avatars_table.get_item(Key={"avatarId": avatar_id}).get("Item"))
    if not item:
        return Response(status_code=404)
    try:
        obj = await asyncio.to_thread(
            lambda: _s3.get_object(Bucket=AVATARS_BUCKET, Key=item["imageKey"]))
        data = obj["Body"].read()
    except Exception:
        return Response(status_code=404)
    return Response(content=data, media_type=item.get("contentType", "image/png"),
                    headers={"Cache-Control": "no-cache"})


async def _is_first_avatar() -> bool:
    return (await asyncio.to_thread(
        lambda: _avatars_table.scan(Select="COUNT").get("Count", 0))) == 0


@app.post(BASE + "/api/avatars")
async def create_avatar(req: AvatarUpload):
    """Cria avatar a partir de imagem enviada (base64)."""
    if not _avatars_table or not AVATARS_BUCKET:
        return {"error": "avatars não configurado"}
    try:
        raw = base64.b64decode(req.imageBase64.split(",")[-1])
    except Exception:
        return {"error": "imagem inválida"}
    if not raw:
        return {"error": "imagem vazia"}
    avatar_id = "a" + uuid.uuid4().hex[:12]
    ext = "png" if "png" in req.contentType.lower() else "jpg"
    key = f"avatars/{avatar_id}.{ext}"
    await asyncio.to_thread(
        lambda: _s3.put_object(Bucket=AVATARS_BUCKET, Key=key, Body=raw, ContentType=req.contentType))
    is_first = await _is_first_avatar()
    item = {
        "avatarId": avatar_id, "name": (req.name or "").strip() or "Avatar",
        "imageKey": key, "contentType": req.contentType,
        "calibration": _to_decimal(DEFAULT_FACE), "gender": "female", "isDefault": is_first,
        "createdAt": datetime.now().isoformat(),
    }
    await asyncio.to_thread(lambda: _avatars_table.put_item(Item=item))
    return {"id": avatar_id, "isDefault": is_first}


@app.post(BASE + "/api/avatars/generate")
async def generate_avatar(req: AvatarGenerate):
    """Gera um retrato frontal via Amazon Nova Canvas e cria o avatar."""
    if not _avatars_table or not AVATARS_BUCKET:
        return {"error": "avatars não configurado"}
    # A descrição do usuário vem PRIMEIRO (pesa mais); os descritores de estilo complementam.
    user_desc = (req.prompt or "").strip()
    head = (f"{user_desc}. " if user_desc else "")
    common = ("front-facing, looking directly at the camera, centered symmetrical face, "
              "head and shoulders visible, plain simple background")
    style = (req.style or "desenho").strip().lower()
    if style in ("desenho", "ilustracao", "ilustração", "illustration", "drawing"):
        prompt = head + ("flat 2D vector illustration portrait, modern digital drawing, clean line "
                         f"art with soft cel shading, friendly corporate character style, {common}")
        negative = ("photograph, photorealistic, realistic photo, 3d render, side profile, "
                    "multiple people, text, watermark, logo, blurry, deformed")
    elif style in ("cartoon", "3d", "cartoon3d"):
        prompt = head + (f"stylized 3D cartoon character portrait, Pixar-style render, expressive, "
                         f"{common}, soft studio lighting")
        negative = ("photograph, photorealistic, side profile, multiple people, text, watermark, "
                    "logo, blurry, deformed")
    else:  # realista
        prompt = head + (f"professional corporate headshot portrait, {common}, soft even studio "
                         "lighting, photorealistic, high detail")
        negative = ("side profile, looking away, multiple people, hands near face, text, watermark, "
                    "logo, blurry, low quality, cartoon, illustration")
    prompt = prompt.strip()
    if IMAGE_MODEL_ID.startswith("stability."):
        # Stable Image (Ultra/Core/SD3) — retrato 1:1 fotorrealista, cross-region us-west-2.
        body = {
            "prompt": prompt[:2000], "negative_prompt": negative[:2000],
            "mode": "text-to-image", "aspect_ratio": "1:1", "output_format": "png",
            "seed": random.randint(0, 4294967294),
        }
    else:  # Amazon Nova Canvas
        body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": prompt[:1024], "negativeText": negative},
            "imageGenerationConfig": {"numberOfImages": 1, "height": 512, "width": 512,
                                      "cfgScale": 8.0, "seed": random.randint(0, 858993459)},
        }
    try:
        resp = await asyncio.to_thread(lambda: _bedrock_img.invoke_model(
            modelId=IMAGE_MODEL_ID, contentType="application/json",
            accept="application/json", body=json.dumps(body)))
        payload = json.loads(resp["body"].read())
        b64 = payload["images"][0]
        raw = base64.b64decode(b64)
    except Exception as e:  # noqa: BLE001
        return {"error": f"falha na geração de imagem: {e}"}
    avatar_id = "a" + uuid.uuid4().hex[:12]
    key = f"avatars/{avatar_id}.png"
    await asyncio.to_thread(
        lambda: _s3.put_object(Bucket=AVATARS_BUCKET, Key=key, Body=raw, ContentType="image/png"))
    is_first = await _is_first_avatar()
    item = {
        "avatarId": avatar_id, "name": (req.name or "").strip() or "Avatar gerado",
        "imageKey": key, "contentType": "image/png",
        "calibration": _to_decimal(DEFAULT_FACE), "gender": "female", "isDefault": is_first,
        "createdAt": datetime.now().isoformat(),
    }
    await asyncio.to_thread(lambda: _avatars_table.put_item(Item=item))
    return {"id": avatar_id, "isDefault": is_first}


@app.put(BASE + "/api/avatars/{avatar_id}")
async def update_avatar(avatar_id: str, req: AvatarUpdate):
    """Atualiza nome e/ou calibração do avatar."""
    if not _avatars_table:
        return {"error": "avatars não configurado"}
    exprs, names, values = [], {}, {}
    if req.name is not None:
        exprs.append("#n = :n"); names["#n"] = "name"; values[":n"] = req.name.strip()
    if req.gender is not None:
        exprs.append("#g = :g"); names["#g"] = "gender"; values[":g"] = req.gender.strip().lower()
    if req.calibration is not None:
        exprs.append("#c = :c"); names["#c"] = "calibration"; values[":c"] = _to_decimal(req.calibration)
    if not exprs:
        return {"error": "nada a atualizar"}
    await asyncio.to_thread(lambda: _avatars_table.update_item(
        Key={"avatarId": avatar_id}, UpdateExpression="SET " + ", ".join(exprs),
        ExpressionAttributeNames=names, ExpressionAttributeValues=values))
    return {"id": avatar_id}


@app.put(BASE + "/api/avatars/{avatar_id}/default")
async def set_default_avatar(avatar_id: str):
    """Define este avatar como padrão (limpa o flag dos demais)."""
    if not _avatars_table:
        return {"error": "avatars não configurado"}

    def _apply():
        for i in _avatars_table.scan().get("Items", []):
            want = i["avatarId"] == avatar_id
            if bool(i.get("isDefault", False)) != want:
                _avatars_table.update_item(
                    Key={"avatarId": i["avatarId"]},
                    UpdateExpression="SET isDefault = :d", ExpressionAttributeValues={":d": want})

    await asyncio.to_thread(_apply)
    return {"id": avatar_id, "isDefault": True}


@app.delete(BASE + "/api/avatars/{avatar_id}")
async def delete_avatar(avatar_id: str):
    if not _avatars_table:
        return {"error": "avatars não configurado"}
    item = await asyncio.to_thread(
        lambda: _avatars_table.get_item(Key={"avatarId": avatar_id}).get("Item"))
    if not item:
        return {"error": "não encontrado"}
    was_default = bool(item.get("isDefault", False))
    try:
        await asyncio.to_thread(
            lambda: _s3.delete_object(Bucket=AVATARS_BUCKET, Key=item["imageKey"]))
    except Exception:
        pass
    await asyncio.to_thread(lambda: _avatars_table.delete_item(Key={"avatarId": avatar_id}))
    # Se apagou o padrão, promove o avatar mais antigo remanescente.
    if was_default:
        rest = await asyncio.to_thread(lambda: _avatars_table.scan().get("Items", []))
        rest.sort(key=lambda x: x.get("createdAt", ""))
        if rest:
            await asyncio.to_thread(lambda: _avatars_table.update_item(
                Key={"avatarId": rest[0]["avatarId"]},
                UpdateExpression="SET isDefault = :d", ExpressionAttributeValues={":d": True}))
    return {"deleted": avatar_id}


@app.get(BASE + "/api/vagas")
async def list_vagas():
    if not _vagas_table:
        return {"vagas": []}
    items = (await asyncio.to_thread(lambda: _vagas_table.scan().get("Items", [])))
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return {"vagas": [{"id": i["vagaId"], "title": i.get("title", ""),
                       "description": i.get("description", ""), "createdAt": i.get("createdAt", "")}
                      for i in items]}


class VagaRequest(BaseModel):
    title: str
    description: str


@app.post(BASE + "/api/vagas")
async def create_vaga(req: VagaRequest):
    if not _vagas_table:
        return {"error": "tabela de vagas não configurada"}
    item = {"vagaId": "v" + uuid.uuid4().hex[:12], "title": req.title.strip(),
            "description": req.description.strip(), "createdAt": datetime.now().isoformat()}
    await asyncio.to_thread(lambda: _vagas_table.put_item(Item=item))
    return {"id": item["vagaId"], **item}


@app.put(BASE + "/api/vagas/{vaga_id}")
async def update_vaga(vaga_id: str, req: VagaRequest):
    if not _vagas_table:
        return {"error": "tabela de vagas não configurada"}
    # Atualiza título/descrição preservando createdAt (usa nomes escapados por segurança).
    await asyncio.to_thread(lambda: _vagas_table.update_item(
        Key={"vagaId": vaga_id},
        UpdateExpression="SET #t = :t, #d = :d",
        ExpressionAttributeNames={"#t": "title", "#d": "description"},
        ExpressionAttributeValues={":t": req.title.strip(), ":d": req.description.strip()}))
    return {"id": vaga_id, "title": req.title.strip(), "description": req.description.strip()}


@app.delete(BASE + "/api/vagas/{vaga_id}")
async def delete_vaga(vaga_id: str):
    if not _vagas_table:
        return {"error": "tabela de vagas não configurada"}
    await asyncio.to_thread(lambda: _vagas_table.delete_item(Key={"vagaId": vaga_id}))
    return {"deleted": vaga_id}


@app.websocket(BASE + "/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session = None

    async def process_output():
        """Read Nova Sonic output and forward audio/text to the browser."""
        try:
            current_role = ""
            is_speculative = False
            receiver = session.receiver

            while session and session.is_active:
                result = await receiver.receive()
                if result is None:
                    break

                if result.value and result.value.bytes_:
                    data = json.loads(result.value.bytes_.decode("utf-8"))
                    evt = data.get("event", {})

                    if "audioOutput" in evt:
                        await ws.send_json({
                            "type": "audio",
                            "content": evt["audioOutput"]["content"],
                        })
                    elif "textOutput" in evt:
                        role = evt["textOutput"].get("role", "")
                        text = evt["textOutput"]["content"]
                        await ws.send_json({
                            "type": "text",
                            "content": text,
                            "role": role,
                        })
                        # Collect transcript
                        if role == "USER":
                            session.transcript.append({"role": "Candidato", "text": text})
                        elif role == "ASSISTANT" and is_speculative:
                            session.transcript.append({"role": "Entrevistador", "text": text})
                    elif "contentStart" in evt:
                        cs = evt["contentStart"]
                        current_role = cs.get("role", "")
                        additional = cs.get("additionalModelFields")
                        is_speculative = False
                        if additional:
                            try:
                                fields = json.loads(additional)
                                is_speculative = fields.get("generationStage") == "SPECULATIVE"
                            except Exception:
                                pass
                        await ws.send_json({
                            "type": "content_start",
                            "role": current_role,
                            "speculative": is_speculative,
                        })
                    elif "usageEvent" in evt:
                        ue = evt["usageEvent"]
                        total = ue.get("details", {}).get("total", {})
                        inp = total.get("input", {})
                        out = total.get("output", {})
                        session.token_usage.update({
                            "input_speech": inp.get("speechTokens", 0),
                            "input_text": inp.get("textTokens", 0),
                            "output_speech": out.get("speechTokens", 0),
                            "output_text": out.get("textTokens", 0),
                            "total_input": ue.get("totalInputTokens", 0),
                            "total_output": ue.get("totalOutputTokens", 0),
                            "total": ue.get("totalTokens", 0),
                        })
                    elif "contentEnd" in evt:
                        ce = evt["contentEnd"]
                        stop_reason = ce.get("stopReason", "")
                        if stop_reason == "INTERRUPTED":
                            session.interruption_count += 1
                            session.transcript.append({
                                "role": "Sistema",
                                "text": f"[Candidato interrompeu o entrevistador — interrupção #{session.interruption_count}]"
                            })
                            # Tell frontend to clear audio queue
                            await ws.send_json({"type": "barge_in"})
        except Exception as e:
            if session and session.is_active:
                print(f"Output processing error: {e}")
                try:
                    await ws.send_json({"type": "error", "message": str(e)})
                except Exception:
                    pass

    output_task = None

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "start":
                job_description = msg.get("job_description", "General software engineering position")
                av_name, av_gender = await asyncio.to_thread(_default_avatar_meta)
                session = NovaSonicSession(job_description, av_name, av_gender)
                # Open the stream
                session.stream = await session.client.invoke_model_with_bidirectional_stream(
                    InvokeModelWithBidirectionalStreamOperationInput(model_id=MODEL_ID)
                )
                session.is_active = True

                # Must run await_output() concurrently with sending events
                async def setup_receiver():
                    output = await session.stream.await_output()
                    session.receiver = output[1]

                await asyncio.gather(setup_receiver(), session.send_setup_events())

                # Now start the output processing loop
                output_task = asyncio.create_task(process_output())
                await ws.send_json({"type": "session_started"})

            elif msg_type == "audio" and session:
                await session.send_audio(msg["content"])

            elif msg_type == "stop":
                transcript_data = []
                job_desc = ""
                token_usage = {}
                recorder = None
                if session:
                    transcript_data = session.transcript
                    job_desc = session.job_description
                    token_usage = session.token_usage.copy()
                    recorder = session.recorder
                    await session.stop()
                    session = None
                if output_task:
                    output_task.cancel()
                    output_task = None
                await ws.send_json({"type": "session_stopped", "token_usage": token_usage})

                # Generate report in a thread (boto3 is blocking)
                report_text = ""
                if transcript_data:
                    await ws.send_json({"type": "report_generating"})
                    try:
                        report_text = await asyncio.to_thread(
                            generate_report_sync, job_desc, transcript_data
                        )
                        await ws.send_json({
                            "type": "report",
                            "content": report_text,
                            "token_usage": token_usage,
                        })
                    except Exception as e:
                        print(f"Report generation error: {e}")
                        await ws.send_json({"type": "error", "message": f"Erro ao gerar relatório: {e}"})

                # Save recording in a thread (ffmpeg is blocking)
                if recorder:
                    asyncio.get_event_loop().run_in_executor(
                        None, recorder.save, transcript_data, report_text, token_usage
                    )

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if session:
            await session.stop()
        if output_task:
            output_task.cancel()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
