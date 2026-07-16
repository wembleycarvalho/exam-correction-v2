"""API router único (HTTP API, rota catch-all ANY /api/{proxy+}).

Roteia por método + path. Autorização: header secreto de origem (só CloudFront) + claims
do JWT Cognito (já validado pelo authorizer nativo). A API NÃO invoca o Runtime para
correção (isso é do worker); apenas registra/consulta submissões e faz o CRUD de admin.
O wizard de resposta (author) é a única invocação síncrona de agente aqui.
"""
import json
import os
import re
import time
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from common import http, authz, metrics
from common.ids import generate_test_id
from common.model_config import get_model_config, CAPABILITIES
from common.runtime_client import invoke_agent

SUBMISSIONS_TABLE = os.environ["SUBMISSIONS_TABLE"]
CORRECTIONS_TABLE = os.environ["CORRECTIONS_TABLE"]
RUBRICS_TABLE = os.environ["RUBRICS_TABLE"]
EXAMS_TABLE = os.environ["EXAMS_TABLE"]
MODEL_CONFIG_TABLE = os.environ["MODEL_CONFIG_TABLE"]
TEST_REGISTRY_TABLE = os.environ["TEST_REGISTRY_TABLE"]
UPLOAD_BUCKET = os.environ["UPLOAD_BUCKET"]
QUEUE_URL = os.environ["QUEUE_URL"]
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

_ddb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")
_sqs = boto3.client("sqs")
_cw = boto3.client("cloudwatch")
_idp = boto3.client("cognito-idp")
_bedrock = boto3.client("bedrock")

_ALLOWED_TYPES = {"essay", "exam", "answersheet"}
_ALLOWED_EXT = {"png", "jpg", "jpeg", "pdf", "webp", "gif"}


# ================================ Router ========================================
def handler(event, _context=None):
    if not authz.verify_origin(event):
        return http.error(403, http.FORBIDDEN, "Acesso permitido apenas via CloudFront.")

    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "") or ""
    segs = [s for s in path.split("/") if s]  # ex.: ["api","submissions","<id>"]
    if segs and segs[0] == "api":
        segs = segs[1:]

    try:
        return _route(event, method, segs)
    except PermissionError as exc:
        return http.error(403, http.FORBIDDEN, str(exc) or "Ação restrita a administradores.")
    except ValueError:
        # inclui json.JSONDecodeError (corpo inválido)
        return http.error(400, http.INVALID_BODY, "Corpo JSON inválido ou campos incorretos.")
    except KeyError:
        return http.error(400, http.INVALID_BODY, "Campos obrigatórios ausentes.")
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return http.error(500, "INTERNAL", "Erro interno ao processar a requisição.")


def _route(event, method, segs):
    if not segs:
        return http.error(404, http.NOT_FOUND, "Recurso não encontrado.")
    head = segs[0]

    if head == "health":
        return http.response(200, {"status": "ok"})
    if head == "submissions":
        return _submissions(event, method, segs)
    if head == "corrections":
        return _corrections(event, method, segs)
    if head == "rubrics":
        return _crud_versioned(event, method, segs, RUBRICS_TABLE, "rubricId", "rubrics")
    if head == "exams":
        return _exams(event, method, segs)
    if head == "model-config":
        return _model_config(event, method, segs)
    if head == "test-registry":
        return _test_registry(event, method, segs)
    if head == "analytics":
        return _analytics(event)
    if head == "evaluations":
        return _evaluations(event, method, segs)
    if head == "models":
        return _models(event)
    if head == "card-templates":
        return _card_templates(event, method, segs)
    if head == "pricing":
        return _pricing_route(event, method)
    if head == "admin" and len(segs) >= 2 and segs[1] == "users":
        return _admin_users(event, method)
    return http.error(404, http.NOT_FOUND, "Recurso não encontrado.")


# ============================== Submissions =====================================
def _submissions(event, method, segs):
    owner = authz.get_owner_id(event)
    # /submissions
    if len(segs) == 1:
        if method == "POST":
            return _create_submission(event, owner)
        if method == "GET":
            return _list_submissions(event, owner)
        return _405()
    # /submissions/{id}[/confirm]
    sub_id = segs[1]
    if len(segs) == 3 and segs[2] == "confirm" and method == "POST":
        return _confirm_submission(sub_id, owner, event)
    if len(segs) == 3 and segs[2] == "corrections" and method == "GET":
        return _get_corrections(sub_id, owner, event)
    if len(segs) == 3 and segs[2] == "image" and method == "GET":
        return _get_image(sub_id, owner, event)
    if len(segs) == 3 and segs[2] == "transcription-rating" and method == "PUT":
        return _rate_transcription(sub_id, owner, event)
    if len(segs) == 3 and segs[2] == "answersheet-result" and method == "POST":
        return _save_answersheet_result(sub_id, owner, event)
    if len(segs) == 2 and method == "GET":
        return _get_submission(sub_id, owner, event)
    return _405()


def _rate_transcription(sub_id, owner, event):
    """Avaliação (👍/👎) de uma transcrição específica da submissão.

    A transcrição vive em submission.result.transcriptions[index]; grava o campo `rating`
    ("up"/"down"/"") nesse elemento da lista. Usado depois na Evaluation/analytics.
    """
    body = http.parse_json_body(event)
    idx = body.get("index")
    if not isinstance(idx, int) or isinstance(idx, bool):
        return http.error(400, http.INVALID_BODY, "index inválido.")
    rating = _norm_rating(body.get("rating"))
    table = _ddb.Table(SUBMISSIONS_TABLE)
    sub = table.get_item(Key={"submissionId": sub_id}).get("Item")
    if not sub:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if sub.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    trs = (sub.get("result") or {}).get("transcriptions") or []
    if idx < 0 or idx >= len(trs):
        return http.error(404, http.NOT_FOUND, "Transcrição não encontrada.")
    table.update_item(
        Key={"submissionId": sub_id},
        UpdateExpression=f"SET #r.transcriptions[{idx}].#rt = :v, updatedAt = :t",
        ExpressionAttributeNames={"#r": "result", "#rt": "rating"},
        ExpressionAttributeValues={":v": rating, ":t": _now()},
    )
    return http.response(200, {"submissionId": sub_id, "index": idx, "rating": rating})


def _save_answersheet_result(sub_id, owner, event):
    """Salva no histórico uma leitura de cartão feita no cliente (OpenCV.js), sem passar
    pelo worker. A submissão já foi criada (PENDING_UPLOAD) e a imagem enviada ao S3."""
    body = http.parse_json_body(event)
    answers = body.get("answers")
    if not isinstance(answers, list):
        return http.error(400, http.INVALID_BODY, "answers deve ser uma lista.")
    table = _ddb.Table(SUBMISSIONS_TABLE)
    sub = table.get_item(Key={"submissionId": sub_id}).get("Item")
    if not sub:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if sub.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    if sub.get("type") != "answersheet":
        return http.error(400, http.INVALID_BODY, "Submissão não é de cartão-resposta.")
    clean = []
    for a in answers:
        try:
            item_a = {"questao": int(a.get("questao")), "marcada": str(a.get("marcada", ""))[:2]}
            if isinstance(a.get("marcadas"), list):
                item_a["marcadas"] = [str(x)[:2] for x in a.get("marcadas")]
            clean.append(item_a)
        except (TypeError, ValueError):
            continue
    reading = {"index": 0, "model": str(body.get("source", "OpenCV (navegador)")),
               "isChallenger": False, "answers": clean, "tokensIn": 0, "tokensOut": 0,
               "source": "opencv"}
    id_exam = (body.get("idExam") or "").strip()[:200]
    names = {"#s": "status", "#r": "result"}
    values = {":d": "DONE",
              ":r": _to_ddb({"readings": [reading], "templateId": body.get("templateId", ""),
                             "source": "opencv"}),
              ":t": _now()}
    expr = "SET #s = :d, #r = :r, updatedAt = :t"
    if id_exam:
        expr += ", idExam = :ix"
        values[":ix"] = id_exam
    table.update_item(Key={"submissionId": sub_id}, UpdateExpression=expr,
                      ExpressionAttributeNames=names, ExpressionAttributeValues=values)
    return http.response(200, {"submissionId": sub_id, "status": "DONE",
                               "count": len(clean), "idExam": id_exam})


# ============================== Corrections =====================================
def _corrections(event, method, segs):
    # /corrections/{id}/rating
    if len(segs) == 3 and segs[2] == "rating" and method == "PUT":
        return _rate_correction(segs[1], event)
    return _405()


def _rate_correction(cid, event):
    """Avaliação (👍/👎) de uma correção. Grava `rating` ("up"/"down"/"") no registro."""
    body = http.parse_json_body(event)
    rating = _norm_rating(body.get("rating"))
    table = _ddb.Table(CORRECTIONS_TABLE)
    item = table.get_item(Key={"correctionId": cid}).get("Item")
    if not item:
        return http.error(404, http.NOT_FOUND, "Correção não encontrada.")
    if item.get("ownerId") != authz.get_owner_id(event) and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta correção.")
    table.update_item(
        Key={"correctionId": cid},
        UpdateExpression="SET #rt = :v, updatedAt = :t",
        ExpressionAttributeNames={"#rt": "rating"},
        ExpressionAttributeValues={":v": rating, ":t": _now()},
    )
    return http.response(200, {"correctionId": cid, "rating": rating})


def _norm_rating(v) -> str:
    v = v.strip().lower() if isinstance(v, str) else ""
    return v if v in ("up", "down") else ""


def _get_image(sub_id, owner, event):
    """URL pré-assinada (GET) do arquivo original enviado, para revisão na UI."""
    sub = _ddb.Table(SUBMISSIONS_TABLE).get_item(Key={"submissionId": sub_id}).get("Item")
    if not sub:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if sub.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    key = sub.get("s3Key", "")
    url = _s3.generate_presigned_url("get_object",
                                     Params={"Bucket": UPLOAD_BUCKET, "Key": key}, ExpiresIn=600)
    return http.response(200, {"url": url, "ext": key.rsplit(".", 1)[-1].lower()})


def _get_corrections(sub_id, owner, event):
    """Correções (por rubrica/estratégia; inclui challenger) de uma submissão."""
    sub = _ddb.Table(SUBMISSIONS_TABLE).get_item(Key={"submissionId": sub_id}).get("Item")
    if not sub:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if sub.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    items = _ddb.Table(CORRECTIONS_TABLE).query(
        IndexName="bySubmission",
        KeyConditionExpression=Key("submissionId").eq(sub_id),
    ).get("Items", [])
    return http.response(200, {"submission": sub, "corrections": items})


def _create_submission(event, owner):
    body = http.parse_json_body(event)
    stype = body.get("type")
    if stype not in _ALLOWED_TYPES:
        return http.error(400, http.INVALID_BODY, "type deve ser 'essay' ou 'exam'.")
    ext = str(body.get("fileExt", "png")).lower()
    if ext not in _ALLOWED_EXT:
        return http.error(400, http.INVALID_BODY, "Formato de arquivo não suportado.")
    sub_id = uuid.uuid4().hex
    s3_key = f"uploads/{stype}/{sub_id}/original.{ext}"
    content_type = "application/pdf" if ext == "pdf" else f"image/{'jpeg' if ext == 'jpg' else ext}"
    upload_url = _s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": UPLOAD_BUCKET, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=900,
    )
    _ddb.Table(SUBMISSIONS_TABLE).put_item(Item={
        "submissionId": sub_id, "type": stype, "status": "PENDING_UPLOAD",
        "ownerId": owner, "s3Key": s3_key, "options": body.get("options", {}) or {},
        "createdAt": _now(), "updatedAt": _now(),
    })
    return http.response(201, {"submissionId": sub_id, "uploadUrl": upload_url, "s3Key": s3_key})


def _confirm_submission(sub_id, owner, event):
    table = _ddb.Table(SUBMISSIONS_TABLE)
    item = table.get_item(Key={"submissionId": sub_id}).get("Item")
    if not item:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if item.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    try:
        _s3.head_object(Bucket=UPLOAD_BUCKET, Key=item["s3Key"])
    except Exception:  # noqa: BLE001
        return http.error(400, "UPLOAD_MISSING", "Arquivo ainda não foi enviado.")
    table.update_item(
        Key={"submissionId": sub_id},
        UpdateExpression="SET #s = :q, updatedAt = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":q": "QUEUED", ":t": _now()},
    )
    _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps({"submissionId": sub_id}))
    return http.response(202, {"submissionId": sub_id, "status": "QUEUED"})


def _get_submission(sub_id, owner, event):
    item = _ddb.Table(SUBMISSIONS_TABLE).get_item(Key={"submissionId": sub_id}).get("Item")
    if not item:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if item.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    return http.response(200, item)


def _list_submissions(event, owner):
    qs = event.get("queryStringParameters") or {}
    table = _ddb.Table(SUBMISSIONS_TABLE)
    if qs.get("all") == "true" and authz.has_group(event, "admin"):
        items = table.scan(Limit=100).get("Items", [])
    else:
        items = table.query(
            IndexName="byOwner",
            KeyConditionExpression=Key("ownerId").eq(owner),
            ScanIndexForward=False, Limit=100,
        ).get("Items", [])
    return http.response(200, {"items": items})


# ======================== CRUD versionado (rubrics) =============================
def _crud_versioned(event, method, segs, table_name, pk, label):
    table = _ddb.Table(table_name)
    if len(segs) == 1:
        if method == "GET":
            return http.response(200, {"items": _latest_versions(table, pk)})
        if method == "POST":
            _require_admin(event)
            return _put_versioned(event, table, pk, new_id=True)
        return _405()
    item_id = segs[1]
    if method == "GET":
        latest = _latest_of(table, pk, item_id)
        if not latest:
            return http.error(404, http.NOT_FOUND, f"{label}: não encontrado.")
        return http.response(200, latest)
    if method == "PUT":
        _require_admin(event)
        return _put_versioned(event, table, pk, new_id=False, item_id=item_id)
    return _405()


def _put_versioned(event, table, pk, new_id, item_id=None):
    body = http.parse_json_body(event)
    the_id = uuid.uuid4().hex if new_id else item_id
    latest = _latest_of(table, pk, the_id)
    next_version = str(int(latest["version"]) + 1) if latest else "1"
    item = {**body, pk: the_id, "version": next_version, "updatedAt": _now()}
    table.put_item(Item=item)
    return http.response(201 if new_id else 200, item)


def _latest_of(table, pk, item_id):
    resp = table.query(KeyConditionExpression=Key(pk).eq(item_id), ScanIndexForward=False, Limit=1)
    items = resp.get("Items", [])
    return items[0] if items else None


def _latest_versions(table, pk):
    # Retorna a última versão de cada item (scan simples; volume esperado baixo).
    latest = {}
    for it in table.scan().get("Items", []):
        key = it[pk]
        if key not in latest or int(it.get("version", 0)) > int(latest[key].get("version", 0)):
            latest[key] = it
    return list(latest.values())


# ================================ Exams =========================================
def _exams(event, method, segs):
    # /exams/{id}/suggest-answer
    if len(segs) == 3 and segs[2] == "suggest-answer" and method == "POST":
        _require_admin(event)
        return _suggest_answer(event)
    return _crud_versioned(event, method, segs, EXAMS_TABLE, "examId", "exams")


def _suggest_answer(event):
    body = http.parse_json_body(event)
    question = (body.get("question") or "").strip()
    if not question:
        return http.error(400, http.INVALID_BODY, "Informe a questão.")
    cfg = get_model_config("author")
    if not cfg["primaryModel"]:
        return http.error(409, "MODEL_NOT_CONFIGURED", "Configure o modelo da capacidade 'author'.")
    out = invoke_agent("author", cfg["primaryModel"], {"question": question})
    return http.response(200, out.get("result", {}))


# ============================= Model config =====================================
def _model_config(event, method, segs):
    table = _ddb.Table(MODEL_CONFIG_TABLE)
    if len(segs) == 1 and method == "GET":
        return http.response(200, {"items": [get_model_config(c) for c in CAPABILITIES]})
    if len(segs) == 2:
        capability = segs[1]
        if capability not in CAPABILITIES:
            return http.error(404, http.NOT_FOUND, "Capacidade desconhecida.")
        if method == "GET":
            return http.response(200, get_model_config(capability))
        if method == "PUT":
            _require_admin(event)
            body = http.parse_json_body(event)
            mode = body.get("mode", "single")
            if mode not in ("single", "ab", "both"):
                mode = "single"
            table.put_item(Item={
                "capability": capability,
                "primaryModel": body.get("primaryModel", ""),
                "challengerModel": body.get("challengerModel", ""),
                "mode": mode,
                "abPolicy": {"percent": int((body.get("abPolicy") or {}).get("percent", 0))},
                "updatedAt": _now(),
            })
            return http.response(200, get_model_config(capability))
    return _405()


# ============================ Test registry =====================================
def _test_registry(event, method, segs):
    table = _ddb.Table(TEST_REGISTRY_TABLE)
    owner = authz.get_owner_id(event)
    if len(segs) == 1 and method == "POST":
        body = http.parse_json_body(event)
        test_id = generate_test_id()
        item = {
            "testId": test_id, "ownerId": owner, "revoked": False, "createdAt": _now(),
            **{k: body.get(k) for k in (
                "examId", "examVersion", "studentId", "disciplineId", "classId",
                "academicPeriod", "institutionId") if body.get(k) is not None},
        }
        table.put_item(Item=item)
        return http.response(201, item)
    if len(segs) == 2 and method == "GET":
        item = table.get_item(Key={"testId": segs[1]}).get("Item")
        if not item or item.get("revoked"):
            return http.error(404, http.NOT_FOUND, "TestID não encontrado.")
        return http.response(200, item)
    return _405()


# ============================== Evaluation (judge) ==============================
def _evaluations(event, method, segs):
    if len(segs) == 2 and segs[1] == "candidates" and method == "GET":
        return _eval_candidates(event)
    if len(segs) == 2 and segs[1] == "run" and method == "POST":
        return _eval_run(event)
    return _405()


def _mlabel(model_id: str) -> str:
    """Nome curto do modelo (tira prefixo de região e sufixo de versão/data)."""
    s = re.sub(r"^(global|us|eu|apac)\.", "", model_id or "")
    s = re.sub(r"-\d{8}-v\d+:\d+$", "", s)
    s = re.sub(r"-v\d+:\d+$", "", s)
    return s or (model_id or "—")


def _eval_candidates(event):
    """Submissões DONE que usaram >1 modelo em transcrição OU correção (por tipo)."""
    owner = authz.get_owner_id(event)
    is_admin = authz.has_group(event, "admin")
    subs_t = _ddb.Table(SUBMISSIONS_TABLE)
    if is_admin:
        subs = subs_t.scan().get("Items", [])
    else:
        subs = subs_t.query(IndexName="byOwner",
                            KeyConditionExpression=Key("ownerId").eq(owner)).get("Items", [])
    subs = [s for s in subs if s.get("status") == "DONE"]

    cors = _ddb.Table(CORRECTIONS_TABLE).scan(
        ProjectionExpression="submissionId, modelUsed, transcriptionIndex").get("Items", [])
    by_sub = {}
    for c in cors:
        by_sub.setdefault(c.get("submissionId"), []).append(c)

    out = []
    for s in subs:
        sid = s.get("submissionId")
        trs = (s.get("result") or {}).get("transcriptions") or []
        multi_tr = len(trs) > 1
        groups = {}
        for c in by_sub.get(sid, []):
            groups.setdefault(int(c.get("transcriptionIndex", 0) or 0), []).append(c)
        multi_cor = any(len({c.get("modelUsed") for c in g}) > 1 for g in groups.values())
        if not (multi_tr or multi_cor):
            continue
        evs = (s.get("result") or {}).get("evaluations") or []
        out.append({
            "submissionId": sid, "type": s.get("type"), "createdAt": s.get("createdAt"),
            "grade": (s.get("result") or {}).get("grade"),
            "nTranscriptions": len(trs),
            "multiTranscription": multi_tr, "multiCorrection": multi_cor,
            "transcriptionModels": [_mlabel(t.get("model", "")) for t in trs],
            "correctionModels": sorted({_mlabel(c.get("modelUsed", "")) for c in by_sub.get(sid, [])}),
            "evaluations": evs, "evaluationCount": len(evs),
        })
    out.sort(key=lambda x: x.get("createdAt") or "", reverse=True)
    return http.response(200, {"candidates": out})


def _pairs(items):
    return [(items[i], items[j]) for i in range(len(items)) for j in range(i + 1, len(items))]


def _render_transcription(stype, tr):
    r = (tr or {}).get("result") or {}
    if stype == "exam":
        qa = r.get("transcricao") or []
        return "\n\n".join(f"Questão {i + 1}: {q.get('question', '')}\n"
                           f"Resposta: {q.get('resposta', '')}" for i, q in enumerate(qa))
    return r.get("text", "") or ""


def _render_correction(stype, c):
    r = (c or {}).get("result") or {}
    if stype == "exam":
        qs = r.get("questoes") or []
        body = "\n".join(f"Questão {i + 1}: {q.get('nota')}/{q.get('notaMaxima')} — "
                         f"{q.get('justificativa', '')}" for i, q in enumerate(qs))
        return f"Nota total: {r.get('notaTotal')}\n{body}"
    crits = r.get("criteria") or []
    body = "\n".join(f"{cr.get('name')}: {cr.get('score')}/{cr.get('maxScore')} — "
                     f"{cr.get('feedback', '')}" for cr in crits)
    return f"Nota total: {r.get('totalScore')}\n{body}\nComentário geral: {r.get('feedback', '')}"


def _cmp_out(res, label_a, label_b, meta):
    r = res.get("result", {}) or {}
    u = res.get("usage", {}) or {}
    return {"modelA": label_a, "modelB": label_b, "winner": r.get("winner", ""),
            "scoreA": r.get("scoreA"), "scoreB": r.get("scoreB"),
            "dimensions": r.get("dimensions", []) or [],
            "rationale": r.get("rationale", ""),
            "tokensIn": u.get("tokensIn", 0), "tokensOut": u.get("tokensOut", 0), **meta}


def _to_ddb(o):
    """Converte floats aninhados em Decimal (DynamoDB não aceita float); mantém Decimals."""
    if isinstance(o, float):
        return Decimal(str(o))
    if isinstance(o, list):
        return [_to_ddb(x) for x in o]
    if isinstance(o, dict):
        return {k: _to_ddb(v) for k, v in o.items()}
    return o


def _eval_run(event):
    """Roda o juiz (model as a judge) para uma submissão: compara transcrições entre si e
    correções (do mesmo grupo de transcrição) entre si, indicando a de maior qualidade."""
    body = http.parse_json_body(event)
    sid = (body.get("submissionId") or "").strip()
    judge = (body.get("judgeModel") or "").strip()
    if not sid or not judge:
        return http.error(400, http.INVALID_BODY, "Informe submissionId e judgeModel.")
    owner = authz.get_owner_id(event)
    sub = _ddb.Table(SUBMISSIONS_TABLE).get_item(Key={"submissionId": sid}).get("Item")
    if not sub:
        return http.error(404, http.NOT_FOUND, "Submissão não encontrada.")
    if sub.get("ownerId") != owner and not authz.has_group(event, "admin"):
        return http.error(403, http.FORBIDDEN, "Sem permissão sobre esta submissão.")
    if sub.get("status") != "DONE":
        return http.error(409, "NOT_DONE", "Submissão ainda não concluída.")

    stype = sub.get("type")
    trs = (sub.get("result") or {}).get("transcriptions") or []
    cors = _ddb.Table(CORRECTIONS_TABLE).query(
        IndexName="bySubmission", KeyConditionExpression=Key("submissionId").eq(sid),
    ).get("Items", [])

    tr_cmps, cor_cmps = [], []
    # 1) Transcrições (pares).
    for a, b in _pairs(trs):
        res = invoke_agent("judge", judge, {
            "kind": "transcription",
            "candidateA": _render_transcription(stype, a),
            "candidateB": _render_transcription(stype, b),
        })
        tr_cmps.append(_cmp_out(res, _mlabel(a.get("model", "")), _mlabel(b.get("model", "")),
                                {"indexA": int(a.get("index") or 0),
                                 "indexB": int(b.get("index") or 0)}))

    # 2) Correções por grupo de transcrição (pares dentro do grupo).
    groups = {}
    for c in cors:
        groups.setdefault(int(c.get("transcriptionIndex", 0) or 0), []).append(c)
    for idx, g in sorted(groups.items()):
        if len(g) < 2:
            continue
        ctx = _render_transcription(stype, next((t for t in trs if t.get("index") == idx), {}))
        for a, b in _pairs(g):
            res = invoke_agent("judge", judge, {
                "kind": stype,
                "candidateA": _render_correction(stype, a),
                "candidateB": _render_correction(stype, b),
                "context": ctx,
            })
            cor_cmps.append(_cmp_out(res, _mlabel(a.get("modelUsed", "")),
                                     _mlabel(b.get("modelUsed", "")),
                                     {"transcriptionIndex": idx}))

    evaluation = {
        "evalId": uuid.uuid4().hex, "judgeModel": _mlabel(judge), "judgeModelId": judge,
        "createdAt": _now(), "ranBy": owner, "type": stype,
        "transcriptionComparisons": tr_cmps, "correctionComparisons": cor_cmps,
    }
    # Persiste a avaliação na própria submissão (histórico), sem nova tabela/infra.
    _ddb.Table(SUBMISSIONS_TABLE).update_item(
        Key={"submissionId": sid},
        UpdateExpression=("SET #r.evaluations = list_append("
                          "if_not_exists(#r.evaluations, :e), :n), updatedAt = :t"),
        ExpressionAttributeNames={"#r": "result"},
        ExpressionAttributeValues={":e": [], ":n": [_to_ddb(evaluation)], ":t": _now()},
    )
    return http.response(200, evaluation)


# =============================== Analytics ======================================
def _analytics(_event):
    subs = _ddb.Table(SUBMISSIONS_TABLE).scan(
        ProjectionExpression="#s, #t", ExpressionAttributeNames={"#s": "status", "#t": "type"},
    ).get("Items", [])
    by_status, by_type = {}, {}
    for it in subs:
        by_status[it.get("status", "?")] = by_status.get(it.get("status", "?"), 0) + 1
        by_type[it.get("type", "?")] = by_type.get(it.get("type", "?"), 0) + 1

    # Correções: notas por tipo + uso por modelo (só oficiais, exclui challenger).
    corr = _ddb.Table(CORRECTIONS_TABLE).scan(
        ProjectionExpression="#ty, grade, modelUsed, isChallenger, tokensIn, tokensOut",
        ExpressionAttributeNames={"#ty": "type"},
    ).get("Items", [])
    grades = {"essay": [], "exam": []}
    by_model = {}
    tbm = {}  # modelo -> [tokensIn, tokensOut] (inclui challenger p/ custo real)
    for c in corr:
        m = c.get("modelUsed", "?")
        ti = int(c.get("tokensIn", 0) or 0)
        to = int(c.get("tokensOut", 0) or 0)
        e = tbm.setdefault(m, [0, 0])
        e[0] += ti
        e[1] += to
        by_model[m] = by_model.get(m, 0) + 1
        if c.get("isChallenger"):
            continue
        g = c.get("grade")
        t = c.get("type")
        if g is not None and t in grades:
            try:
                grades[t].append(float(g))
            except (TypeError, ValueError):
                pass

    tokens_by_model = {m: {"in": v[0], "out": v[1], "total": v[0] + v[1]} for m, v in tbm.items()}
    prices = _load_prices()
    cost_by_model = {}
    cost_in = cost_out = 0.0
    for m, v in tbm.items():
        cb = _cost(m, v[0], v[1], prices)
        if cb:
            cost_by_model[m] = cb
            cost_in += cb["in"]
            cost_out += cb["out"]
    tok_in = sum(v[0] for v in tbm.values())
    tok_out = sum(v[1] for v in tbm.values())

    def stats(vals):
        if not vals:
            return {"count": 0, "avg": None, "min": None, "max": None}
        return {"count": len(vals), "avg": round(sum(vals) / len(vals), 1),
                "min": min(vals), "max": max(vals)}

    # Histograma de notas de redação (faixas de 200 até 1000).
    hist = {"0-200": 0, "201-400": 0, "401-600": 0, "601-800": 0, "801-1000": 0}
    for v in grades["essay"]:
        if v <= 200: hist["0-200"] += 1
        elif v <= 400: hist["201-400"] += 1
        elif v <= 600: hist["401-600"] += 1
        elif v <= 800: hist["601-800"] += 1
        else: hist["801-1000"] += 1

    return http.response(200, {
        "submissions": {"total": len(subs), "byStatus": by_status, "byType": by_type},
        "grades": {"essay": stats(grades["essay"]), "exam": stats(grades["exam"]),
                   "essayHistogram": hist},
        "byModel": by_model,
        "tokens": {"in": tok_in, "out": tok_out, "total": tok_in + tok_out},
        "tokensByModel": tokens_by_model,
        "cost": {"in": round(cost_in, 6), "out": round(cost_out, 6), "total": round(cost_in + cost_out, 6)},
        "costByModel": cost_by_model,
    })


def _model_usage_metrics() -> dict:
    """Agrega tokens/custo da namespace EMF (últimas 24h)."""
    end = int(time.time())
    start = end - 24 * 3600
    out = {}
    for metric in ("tokensIn", "tokensOut", "costUsd", "invocations"):
        try:
            resp = _cw.get_metric_statistics(
                Namespace=os.environ.get("METRICS_NAMESPACE", "ExamCorrection"),
                MetricName=metric, StartTime=start, EndTime=end, Period=86400, Statistics=["Sum"],
            )
            pts = resp.get("Datapoints", [])
            out[metric] = round(sum(p.get("Sum", 0) for p in pts), 6)
        except Exception:  # noqa: BLE001
            out[metric] = None
    return out


# ============================== Modelos =========================================
def _models(_event):
    """Lista modelos MULTIMODAIS (aceitam imagem) invocáveis via Bedrock.

    Inclui inference profiles (recomendados; vários modelos só rodam via profile) e
    foundation models on-demand. Popula os selects da Configuração de Modelos. Quando um
    AgentCore Gateway/Mantle for provisionado, os modelos do Mantle entram aqui também.
    """
    # 1) Foundation models ATIVOS, multimodais (aceitam imagem), saída de texto.
    active_multi = {}   # modelId -> nome amigável
    ondemand = set()    # modelId invocável on-demand
    try:
        for m in _bedrock.list_foundation_models(byOutputModality="TEXT").get("modelSummaries", []):
            status = (m.get("modelLifecycle") or {}).get("status")
            if status and status != "ACTIVE":
                continue  # exclui LEGACY (evita "Access denied ... Legacy")
            if "IMAGE" not in (m.get("inputModalities") or []):
                continue
            mid = m.get("modelId", "")
            active_multi[mid] = m.get("modelName", mid)
            if "ON_DEMAND" in (m.get("inferenceTypesSupported") or []):
                ondemand.add(mid)
    except Exception:  # noqa: BLE001
        pass

    # 2) Inference profiles cujo modelo subjacente é ativo/multimodal. Um por modelo
    #    subjacente (prefere global > us > eu > apac), removendo duplicações.
    region_pref = {"global": 0, "us": 1, "eu": 2, "apac": 3}
    best = {}  # underlyingModelId -> {"id", "pref"}
    try:
        token = None
        while True:
            kw = {"maxResults": 100}
            if token:
                kw["nextToken"] = token
            resp = _bedrock.list_inference_profiles(**kw)
            for p in resp.get("inferenceProfileSummaries", []):
                pid = p.get("inferenceProfileId", "")
                underlying = None
                for a in p.get("models", []):
                    u = a.get("modelArn", "").split("foundation-model/")[-1]
                    if u in active_multi:
                        underlying = u
                        break
                if not underlying:
                    continue
                pref = region_pref.get(pid.split(".", 1)[0], 9)
                cur = best.get(underlying)
                if not cur or pref < cur["pref"]:
                    best[underlying] = {"id": pid, "pref": pref}
            token = resp.get("nextToken")
            if not token:
                break
    except Exception:  # noqa: BLE001
        pass

    # 3) Um item por modelo: profile preferido; senão on-demand. Sem duplicatas.
    out = []
    for mid, name in active_multi.items():
        if mid in best:
            out.append({"id": best[mid]["id"], "label": name, "kind": "profile"})
        elif mid in ondemand:
            out.append({"id": mid, "label": name, "kind": "on-demand"})
    out.sort(key=lambda x: x["label"])
    return http.response(200, {"models": out})


# ========================= Templates de cartão-resposta =========================
# Guardados na tabela model_config com chave "tmpl#<id>" (sem nova tabela/infra).
_TMPL_PREFIX = "tmpl#"


def _card_templates(event, method, segs):
    table = _ddb.Table(MODEL_CONFIG_TABLE)
    if len(segs) == 1:
        if method == "GET":
            items = [_tmpl_public(i) for i in table.scan().get("Items", [])
                     if str(i.get("capability", "")).startswith(_TMPL_PREFIX)]
            items.sort(key=lambda x: x.get("name", ""))
            return http.response(200, {"items": items})
        if method == "POST":
            _require_admin(event)
            return _save_template(event, table, uuid.uuid4().hex, created=True)
        return _405()
    tid = segs[1]
    if len(segs) == 3 and segs[2] == "reference":
        return _template_reference(event, method, tid, table)
    if method == "GET":
        item = table.get_item(Key={"capability": _TMPL_PREFIX + tid}).get("Item")
        if not item:
            return http.error(404, http.NOT_FOUND, "Template não encontrado.")
        return http.response(200, _tmpl_public(item))
    if method == "PUT":
        _require_admin(event)
        return _save_template(event, table, tid, created=False)
    if method == "DELETE":
        _require_admin(event)
        table.delete_item(Key={"capability": _TMPL_PREFIX + tid})
        return http.response(200, {"deleted": tid})
    return _405()


def _save_template(event, table, tid, created):
    body = http.parse_json_body(event)
    name = (body.get("name") or "").strip()
    if not name:
        return http.error(400, http.INVALID_BODY, "Informe o nome do template.")
    default_alt = int(body.get("alternatives") or 5)
    sensitivity = max(5, min(95, int(body.get("sensitivity") or 50)))
    blocks = []
    for b in (body.get("blocks") or []):
        rect = b.get("rect") or {}
        blocks.append({
            "firstQuestion": int(b.get("firstQuestion") or 1),
            "questions": int(b.get("questions") or 0),
            "alternatives": int(b.get("alternatives") or default_alt),
            "rect": {k: float(rect.get(k, 0)) for k in ("x", "y", "w", "h")},
        })
    # alternativas do template = maior nº de alternativas entre os blocos (define as letras).
    alternatives = max([default_alt] + [b["alternatives"] for b in blocks]) if blocks else default_alt
    letters = body.get("letters") or [chr(65 + i) for i in range(alternatives)]
    # Referência de imagem vai para o S3 (chave), não base64 no DynamoDB. Preserva ao editar.
    ref_key = ""
    if not created:
        existing = table.get_item(Key={"capability": _TMPL_PREFIX + tid}).get("Item") or {}
        ref_key = existing.get("referenceKey", "") or ""
    item = {
        "capability": _TMPL_PREFIX + tid, "templateId": tid, "name": name,
        "alternatives": alternatives, "letters": letters, "blocks": blocks,
        "sensitivity": sensitivity, "referenceKey": ref_key, "updatedAt": _now(),
    }
    table.put_item(Item=_to_ddb(item))
    return http.response(201 if created else 200, _tmpl_public(item))


def _template_reference(event, method, tid, table):
    """Gerencia a imagem de referência do template no S3 (para alinhamento automático).
    POST → URL pré-assinada de upload (grava a chave no template). GET → URL de leitura."""
    key_pk = _TMPL_PREFIX + tid
    item = table.get_item(Key={"capability": key_pk}).get("Item")
    if not item:
        return http.error(404, http.NOT_FOUND, "Template não encontrado.")
    if method == "POST":
        _require_admin(event)
        s3key = f"templates/{tid}/reference.jpg"
        url = _s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": UPLOAD_BUCKET, "Key": s3key, "ContentType": "image/jpeg"},
            ExpiresIn=900)
        table.update_item(
            Key={"capability": key_pk},
            UpdateExpression="SET referenceKey = :k, updatedAt = :t",
            ExpressionAttributeValues={":k": s3key, ":t": _now()})
        return http.response(200, {"uploadUrl": url, "key": s3key})
    if method == "GET":
        s3key = item.get("referenceKey", "")
        if not s3key:
            return http.error(404, http.NOT_FOUND, "Template sem imagem de referência.")
        url = _s3.generate_presigned_url(
            "get_object", Params={"Bucket": UPLOAD_BUCKET, "Key": s3key}, ExpiresIn=600)
        return http.response(200, {"url": url})
    return _405()


def _tmpl_public(item):
    d = {k: v for k, v in item.items() if k != "capability"}
    d.pop("referenceImage", None)  # legado (não usamos mais base64)
    d["totalQuestions"] = sum(int(b.get("questions", 0)) for b in (d.get("blocks") or []))
    d["hasReference"] = bool(item.get("referenceKey"))
    return d


# ============================== Preços por modelo ================================
def _pricing_route(event, method):
    """Preços editáveis por modelo (USD por 1k tokens). Guardados como item especial
    na tabela model_config. Família serve de fallback/estimativa (ver common.metrics)."""
    table = _ddb.Table(MODEL_CONFIG_TABLE)
    if method == "GET":
        item = table.get_item(Key={"capability": "__pricing__"}).get("Item") or {}
        return http.response(200, {"prices": item.get("prices", {})})
    if method == "PUT":
        _require_admin(event)
        body = http.parse_json_body(event)
        clean = {}
        for m, v in (body.get("prices") or {}).items():
            try:
                clean[m] = {"in": Decimal(str(float(v.get("in", 0)))),
                            "out": Decimal(str(float(v.get("out", 0))))}
            except (TypeError, ValueError):
                continue
        table.put_item(Item={"capability": "__pricing__", "prices": clean, "updatedAt": _now()})
        return http.response(200, {"prices": clean})
    return _405()


def _load_prices() -> dict:
    item = _ddb.Table(MODEL_CONFIG_TABLE).get_item(Key={"capability": "__pricing__"}).get("Item") or {}
    return item.get("prices", {}) or {}


def _resolve_price(model, prices):
    p = prices.get(model)
    if p:
        try:
            return {"in": float(p["in"]), "out": float(p["out"])}
        except (TypeError, ValueError):
            pass
    return metrics.price_for(model)  # fallback por família (estimativa) ou None


def _cost(model, ti, to, prices):
    p = _resolve_price(model, prices)
    if not p:
        return None
    ci = round(ti / 1000.0 * p["in"], 6)
    co = round(to / 1000.0 * p["out"], 6)
    return {"in": ci, "out": co, "total": round(ci + co, 6)}


# ============================== Admin users =====================================
def _admin_users(event, method):
    if method != "POST":
        return _405()
    _require_admin(event)
    if not USER_POOL_ID:
        return http.error(500, "INTERNAL", "User Pool não configurado.")
    body = http.parse_json_body(event)
    email = (body.get("email") or "").strip()
    group = body.get("group", "professor")
    if not email:
        return http.error(400, http.INVALID_BODY, "Informe o e-mail.")
    _idp.admin_create_user(
        UserPoolId=USER_POOL_ID, Username=email,
        UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}],
        DesiredDeliveryMediums=["EMAIL"],
    )
    if group in ("admin", "professor"):
        _idp.admin_add_user_to_group(UserPoolId=USER_POOL_ID, Username=email, GroupName=group)
    return http.response(201, {"email": email, "group": group, "status": "INVITED"})


# ================================ Helpers =======================================
def _require_admin(event):
    if not authz.has_group(event, "admin"):
        raise PermissionError("Ação restrita a administradores.")


def _405():
    return http.error(405, http.METHOD_NOT_ALLOWED, "Método não permitido.")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
