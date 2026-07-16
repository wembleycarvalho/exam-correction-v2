"""Correction Worker — consumidor SQS que orquestra a correção.

Papel: ponte fina `SQS → InvokeAgentRuntime`. NÃO contém lógica de agente. Para cada
submissão:
  1. claim idempotente QUEUED→PROCESSING (condicional);
  2. carrega o arquivo do S3;
  3. resolve `model_config` por capacidade (transcrição e correção independentes);
  4. invoca o agente de transcrição e depois o de correção (essay/exam) no Runtime;
  5. roda o challenger em shadow quando a abPolicy sortear (não afeta a nota oficial);
  6. persiste `corrections`, atualiza a submissão e emite métricas EMF.

Erros transitórios sobem para reentrega da SQS; após maxReceiveCount vão para a DLQ.
Usa ReportBatchItemFailures para reprocessar apenas o item que falhou.
"""
import base64
import json
import os
import time
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key


def _to_ddb(o):
    """Converte float→Decimal recursivamente (DynamoDB não aceita float)."""
    if isinstance(o, float):
        return Decimal(str(o))
    if isinstance(o, list):
        return [_to_ddb(x) for x in o]
    if isinstance(o, dict):
        return {k: _to_ddb(v) for k, v in o.items()}
    return o

from common import metrics
from common.model_config import get_model_config, plan_runs, get_card_template
from common.runtime_client import invoke_agent
from common.gabarito import get_gabarito

SUBMISSIONS_TABLE = os.environ["SUBMISSIONS_TABLE"]
CORRECTIONS_TABLE = os.environ["CORRECTIONS_TABLE"]
RUBRICS_TABLE = os.environ["RUBRICS_TABLE"]
EXAMS_TABLE = os.environ["EXAMS_TABLE"]
UPLOAD_BUCKET = os.environ["UPLOAD_BUCKET"]

_ddb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")


# --- Persistência ---------------------------------------------------------------
def _load_submission(submission_id: str) -> dict:
    return _ddb.Table(SUBMISSIONS_TABLE).get_item(Key={"submissionId": submission_id}).get("Item")


def _claim(submission_id: str) -> bool:
    """Marca →PROCESSING de forma condicional. Bloqueia apenas submissões já DONE
    (idempotência), permitindo que falhas transitórias sejam reprocessadas pela SQS
    até irem para a DLQ."""
    try:
        _ddb.Table(SUBMISSIONS_TABLE).update_item(
            Key={"submissionId": submission_id},
            UpdateExpression="SET #s = :p, updatedAt = :t",
            ConditionExpression="attribute_exists(submissionId) AND #s <> :done",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":p": "PROCESSING", ":done": "DONE", ":t": _now()},
        )
        return True
    except _ddb.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def _finish(submission_id: str, status: str, result: dict = None, error: str = "") -> None:
    expr = {":s": status, ":t": _now()}
    set_parts = ["#s = :s", "updatedAt = :t"]
    if result is not None:
        set_parts.append("#r = :r")
        expr[":r"] = _to_ddb(result)
    if error:
        set_parts.append("errorMessage = :e")
        expr[":e"] = error[:500]
    _ddb.Table(SUBMISSIONS_TABLE).update_item(
        Key={"submissionId": submission_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames={"#s": "status", **({"#r": "result"} if result is not None else {})},
        ExpressionAttributeValues=expr,
    )


def _save_correction(item: dict) -> None:
    _ddb.Table(CORRECTIONS_TABLE).put_item(Item=_to_ddb(item))


def _load_rubric(rubric_id: str) -> dict:
    resp = _ddb.Table(RUBRICS_TABLE).query(
        KeyConditionExpression=Key("rubricId").eq(rubric_id),
        ScanIndexForward=False, Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


# --- Invocação do agente + métrica ----------------------------------------------
def _run(capability: str, model_id: str, agent_input: dict, submission_id: str,
         is_challenger: bool = False) -> dict:
    started = time.time()
    outcome = "success"
    try:
        out = invoke_agent(capability, model_id, agent_input)
        return out
    except Exception:
        outcome = "error"
        raise
    finally:
        # Emite mesmo em erro (tokens podem ser 0). usage vem de `out` quando sucesso.
        usage = (locals().get("out") or {}).get("usage", {}) if outcome == "success" else {}
        metrics.emit_model_usage(
            capability=capability, model=model_id,
            tokens_in=usage.get("tokensIn", 0), tokens_out=usage.get("tokensOut", 0),
            latency_ms=round((time.time() - started) * 1000, 1),
            outcome=outcome, submission_id=submission_id, is_challenger=is_challenger,
        )


# --- Pipelines -------------------------------------------------------------------
def _transcriptions(sub: dict, image_b64: str, ext: str, kind: str) -> list:
    """Executa o(s) modelo(s) de transcrição conforme o plano (single/ab/both).

    Retorna lista de registros de transcrição (1 ou 2), cada um com seu texto/QA e tokens.
    """
    out_list = []
    for i, run in enumerate(plan_runs(get_model_config("transcription"))):
        out = _run("transcription", run["model"],
                   {"imageB64": image_b64, "ext": ext, "kind": kind},
                   sub["submissionId"], run["isChallenger"])
        u = out.get("usage", {})
        out_list.append({
            "index": i, "model": run["model"], "isChallenger": run["isChallenger"],
            "result": out["result"],
            "tokensIn": u.get("tokensIn", 0), "tokensOut": u.get("tokensOut", 0),
        })
    return out_list


def _correct_essay(sub: dict, tr: dict) -> list:
    """Corrige UMA transcrição de redação com o(s) modelo(s) de correção (plano)."""
    options = sub.get("options", {}) or {}
    rubric_ids = options.get("rubricIds") or ["enem"]
    essay_text = (tr.get("result") or {}).get("text", "")
    plan = plan_runs(get_model_config("essay"))
    corrections = []
    for rid in rubric_ids:
        rubric = _load_rubric(rid)
        if not rubric:
            continue
        for run in plan:
            out = _run("essay", run["model"], {"essayText": essay_text, "rubric": rubric},
                       sub["submissionId"], run["isChallenger"])
            corrections.append(_essay_correction(sub, rubric, out, tr, run["isChallenger"]))
    return corrections


def _correct_exam(sub: dict, tr: dict) -> list:
    """Corrige UMA transcrição de prova com o(s) modelo(s) de correção (plano)."""
    options = sub.get("options", {}) or {}
    strategy = options.get("strategy", "model")
    max_q = float(options.get("maxScorePerQuestion", 10.0))
    gabarito = None
    if strategy == "gabarito":
        exam_id = options.get("examId", "")
        gab = get_gabarito(EXAMS_TABLE, exam_id, options.get("examVersion", "")) if exam_id else {"found": False}
        if not gab.get("found"):
            raise ValueError("Estratégia 'gabarito' sem gabarito associado à prova.")
        gabarito = gab["questions"]
    qa_pairs = (tr.get("result") or {}).get("transcricao", [])
    agent_input = {"qaPairs": qa_pairs, "strategy": strategy, "gabarito": gabarito,
                   "maxScorePerQuestion": max_q}
    corrections = []
    for run in plan_runs(get_model_config("exam")):
        out = _run("exam", run["model"], agent_input, sub["submissionId"], run["isChallenger"])
        corrections.append(_exam_correction(sub, out, tr, strategy, run["isChallenger"]))
    return corrections


# --- Construção dos registros de correção ---------------------------------------
def _tr_fields(tr: dict) -> dict:
    return {"transcriptionModel": tr["model"], "transcriptionIndex": tr["index"],
            "transcriptionIsChallenger": tr["isChallenger"]}


def _essay_correction(sub, rubric, out, tr, is_challenger) -> dict:
    result = out["result"]; usage = out.get("usage", {})
    return {
        "correctionId": uuid.uuid4().hex,
        "submissionId": sub["submissionId"], "type": "essay", "ownerId": sub.get("ownerId", ""),
        "rubricId": rubric.get("rubricId"), "rubricVersion": rubric.get("version"),
        "result": result, "grade": result.get("totalScore"),
        "modelUsed": out["model"], **_tr_fields(tr),
        "tokensIn": usage.get("tokensIn", 0), "tokensOut": usage.get("tokensOut", 0),
        "isChallenger": is_challenger, "createdAt": _now(),
    }


def _exam_correction(sub, out, tr, strategy, is_challenger) -> dict:
    result = out["result"]; usage = out.get("usage", {})
    return {
        "correctionId": uuid.uuid4().hex,
        "submissionId": sub["submissionId"], "type": "exam", "ownerId": sub.get("ownerId", ""),
        "strategy": strategy, "result": result, "grade": result.get("notaTotal"),
        "modelUsed": out["model"], **_tr_fields(tr),
        "tokensIn": usage.get("tokensIn", 0), "tokensOut": usage.get("tokensOut", 0),
        "isChallenger": is_challenger, "createdAt": _now(),
    }


# --- Cartão-resposta: OMR server-side (OpenCV) ----------------------------------
def _omr_answersheet(sub: dict, image_b64: str, tmpl: dict) -> None:
    """Leitura determinística do cartão com OpenCV (alinhamento por features + bolhas)."""
    from worker import omr  # import tardio: carrega opencv só aqui
    sub_id = sub["submissionId"]
    image_bytes = base64.b64decode(image_b64)
    ref_bytes = None
    ref_key = tmpl.get("referenceKey")
    if ref_key:
        try:
            ref_bytes = _s3.get_object(Bucket=UPLOAD_BUCKET, Key=ref_key)["Body"].read()
        except Exception:  # noqa: BLE001
            ref_bytes = None
    answers, meta = omr.read_answersheet(image_bytes, tmpl, ref_bytes)
    model = "OMR servidor (alinhado)" if meta.get("aligned") else "OMR servidor (sem alinhamento)"
    reading = {
        "index": 0, "model": model, "isChallenger": False, "answers": answers,
        "tokensIn": 0, "tokensOut": 0, "source": "omr-server",
        "aligned": bool(meta.get("aligned")), "matches": int(meta.get("matches", 0)),
    }
    _finish(sub_id, "DONE", result={
        "readings": [reading], "source": "omr-server",
        "templateId": tmpl.get("templateId", ""),
        "tokens": {"in": 0, "out": 0, "total": 0},
    })


# --- Cartão-resposta: leitura por LLM (fallback sem template) --------------------
def _process_answersheet(sub: dict, image_b64: str, ext: str) -> None:
    """Lê o cartão com o(s) modelo(s) configurados (single/ab/both) e salva as marcações.

    Não há correção: o resultado é a lista de alternativas marcadas por questão. Quando o
    modo for 'both', guarda uma leitura por modelo (comparável depois na Evaluation).
    """
    sub_id = sub["submissionId"]
    tmpl = get_card_template((sub.get("options") or {}).get("templateId"))

    # Caminho preferido (escala p/ lote): OMR determinístico com OpenCV, usando a geometria
    # e a imagem de referência do template. Cai no LLM só se não houver template/blocos.
    if tmpl and tmpl.get("blocks"):
        _omr_answersheet(sub, image_b64, tmpl)
        return

    plan = plan_runs(get_model_config("answersheet"))
    if not plan:
        raise ValueError("Configure o modelo da capacidade 'answersheet' (Configuração de Modelos) "
                         "ou selecione um template (leitura por OMR).")
    expected = None
    readings = []
    for i, run in enumerate(plan):
        out = _run("answersheet", run["model"],
                   {"imageB64": image_b64, "ext": ext, "expected": expected},
                   sub_id, run["isChallenger"])
        u = out.get("usage", {})
        readings.append({
            "index": i, "model": run["model"], "isChallenger": run["isChallenger"],
            "answers": (out["result"] or {}).get("respostas", []),
            "tokensIn": u.get("tokensIn", 0), "tokensOut": u.get("tokensOut", 0),
        })
    t_in = sum(int(r["tokensIn"]) for r in readings)
    t_out = sum(int(r["tokensOut"]) for r in readings)
    _finish(sub_id, "DONE", result={
        "readings": readings,
        "tokens": {"in": t_in, "out": t_out, "total": t_in + t_out},
    })


# --- Processamento de uma submissão ---------------------------------------------
def _detect_and_store_qr(submission_id: str, image_bytes: bytes, ext: str) -> None:
    """Detecta um QR code na imagem e grava seu conteúdo em `idExam` na submissão."""
    if ext == "pdf":
        return  # QR em PDF não suportado por enquanto
    try:
        from worker import omr
        val = omr.detect_qr(image_bytes)
    except Exception:  # noqa: BLE001
        val = ""
    if not val:
        return
    try:
        _ddb.Table(SUBMISSIONS_TABLE).update_item(
            Key={"submissionId": submission_id},
            UpdateExpression="SET idExam = :v, updatedAt = :t",
            ExpressionAttributeValues={":v": val[:200], ":t": _now()})
    except Exception:  # noqa: BLE001
        pass


def _process(submission_id: str) -> None:
    sub = _load_submission(submission_id)
    if not sub:
        return  # nada a fazer; não reenfileira
    if not _claim(submission_id):
        return  # já processada/em processamento (idempotência)

    try:
        obj = _s3.get_object(Bucket=UPLOAD_BUCKET, Key=sub["s3Key"])
        raw = obj["Body"].read()
        image_b64 = base64.b64encode(raw).decode("utf-8")
        ext = sub["s3Key"].rsplit(".", 1)[-1].lower()

        # QR code (ID_Exam) — vale para redação, prova e cartão. Best-effort.
        _detect_and_store_qr(submission_id, raw, ext)

        # Cartão-resposta: apenas leitura das marcações (sem transcrição/correção).
        if sub.get("type") == "answersheet":
            _process_answersheet(sub, image_b64, ext)
            return

        kind = "exam" if sub.get("type") == "exam" else "essay"

        # Matriz: cada transcrição é corrigida pelo(s) modelo(s) de correção.
        transcriptions = _transcriptions(sub, image_b64, ext, kind)
        corrections = []
        for tr in transcriptions:
            corrections.extend(_correct_exam(sub, tr) if kind == "exam" else _correct_essay(sub, tr))

        for c in corrections:
            _save_correction(c)

        # Oficial = transcrição primária (index 0) + correção primária.
        official = next((c for c in corrections
                         if c.get("transcriptionIndex") == 0 and not c["isChallenger"]), None)
        # Tokens da prova = tudo que rodou (todas transcrições + todas correções).
        t_in = sum(int(t.get("tokensIn", 0)) for t in transcriptions) + \
            sum(int(c.get("tokensIn", 0)) for c in corrections)
        t_out = sum(int(t.get("tokensOut", 0)) for t in transcriptions) + \
            sum(int(c.get("tokensOut", 0)) for c in corrections)
        _finish(submission_id, "DONE", result={
            "transcriptions": transcriptions,
            "grade": official.get("grade") if official else None,
            "correctionIds": [c["correctionId"] for c in corrections],
            "tokens": {"in": t_in, "out": t_out, "total": t_in + t_out},
        })
    except Exception as exc:  # noqa: BLE001
        _finish(submission_id, "FAILED", error=str(exc))
        raise  # sobe para reentrega/DLQ


def handler(event, _context=None):
    """Entrada SQS. Retorna batchItemFailures para reprocessar só o que falhou."""
    failures = []
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            _process(body["submissionId"])
        except Exception:  # noqa: BLE001
            failures.append({"itemIdentifier": record.get("messageId")})
    return {"batchItemFailures": failures}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
