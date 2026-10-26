"""Atendimento — Router (Lambda) do módulo no portal (Fase 1: Templates + Campanhas).

Front door = portal, sob /atendimento/*. O browser nunca fala direto com a AWS; só esta
Lambda (com IAM próprio, JWT do Cognito do portal validado pelo HTTP API authorizer).

Porta a lógica do `tools/campaign_tester/server.py` (End User Messaging Social + Customer
Profiles + Connect Outbound Campaigns + Q in Connect) para um Lambda proxy. Reaproveita o
`campaign_lib.py` (co-localizado no bundle).

Rotas (/atendimento/api/*):
  GET  health                         -> ok
  GET  templates                      -> lista templates WhatsApp da WABA (+ status)
  GET  template?metaTemplateId=..     -> preview do template (partes + variáveis)
  GET  campaign/format?metaTemplateId=.. -> colunas esperadas do CSV daquele template
  POST send   {to,metaTemplateId,name,language,header[],bodyVars[]} -> envia 1-1 (transacional)
  POST campaign/send {csv,filename,metaTemplateId,campaignName} -> cria campanha nova + dispara

Config (SSM /atendimento/*, com fallback p/ env e defaults de demo): waba-id,
phone-number-id, campaign-bucket, cp-domain, meta-api-version. A instância Connect, o KB
Wisdom e o phone ARN de origem das campanhas usam os defaults do `campaign_lib` (recursos
compartilhados de demo), sobrescrevíveis por env.
"""
import json
import os
import re

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
_SSM_PREFIX = os.environ.get("SSM_PREFIX", "/atendimento")

_ssm = boto3.client("ssm", region_name=REGION)

# Clientes (mesmos do tester). boto3 recente vem de uma layer.
sm = boto3.client("socialmessaging", region_name=REGION)
cp = boto3.client("customer-profiles", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
q = boto3.client("qconnect", region_name=REGION)
cc = boto3.client("connectcampaignsv2", region_name=REGION)
connect = boto3.client("connect", region_name=REGION)


def _ssm_get(name, default=""):
    try:
        return _ssm.get_parameter(Name=f"{_SSM_PREFIX}/{name}")["Parameter"]["Value"]
    except Exception:  # noqa: BLE001
        return default


# Config (lida 1x no cold start). Defaults de demo = valores do projeto Harness.
_CFG = {
    "waba_id": os.environ.get("WABA_ID") or _ssm_get("waba-id", "waba-b7e8aaaa528c4a73a9dc4212f4323c79"),
    "origin": os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    or _ssm_get("phone-number-id", "phone-number-id-fe268d418d9b4e1296c47f86795987df"),
    "meta_api": os.environ.get("META_API_VERSION") or _ssm_get("meta-api-version", "v20.0"),
    "campaign_bucket": os.environ.get("CAMPAIGN_BUCKET") or _ssm_get("campaign-bucket", ""),
    "cp_domain": os.environ.get("CP_DOMAIN") or _ssm_get("cp-domain", "amazon-connect-connect-demo-ps"),
}

# Propaga p/ o campaign_lib (que lê alguns via env no import) ANTES de importar.
os.environ.setdefault("WABA_ID", _CFG["waba_id"])
import campaign_lib as lib  # noqa: E402


# --------------------------------------------------------------------------- helpers
def _indices(text):
    return sorted({int(n) for n in re.findall(r"\{\{(\d+)\}\}", text or "")})


def _components(meta_template_id):
    d = sm.get_whatsapp_message_template(id=_CFG["waba_id"], metaTemplateId=meta_template_id)
    tpl = d.get("template")
    if isinstance(tpl, (bytes, bytearray)):
        tpl = tpl.decode("utf-8")
    if isinstance(tpl, str):
        tpl = json.loads(tpl)
    return tpl.get("components", []), tpl


def _template_detail(meta_template_id):
    comps, tpl = _components(meta_template_id)
    out = {"name": tpl.get("name"), "language": tpl.get("language"), "parts": []}
    for c in comps:
        ctype = c.get("type")
        if ctype == "HEADER" and c.get("format", "TEXT") == "TEXT" and c.get("text"):
            idx = _indices(c["text"])
            if idx:
                ex = (c.get("example", {}) or {}).get("header_text", [])
                out["parts"].append({"component": "header", "text": c["text"],
                                     "indices": idx, "examples": ex})
        elif ctype == "BODY":
            idx = _indices(c.get("text", ""))
            ew = (c.get("example", {}) or {}).get("body_text", [[]])
            ex = ew[0] if ew else []
            out["parts"].append({"component": "body", "text": c.get("text", ""),
                                 "indices": idx, "examples": ex})
        elif ctype == "FOOTER":
            out["parts"].append({"component": "footer", "text": c.get("text", ""),
                                 "indices": [], "examples": []})
        elif ctype == "BUTTONS":
            out["parts"].append({"component": "buttons", "text": "",
                                 "buttons": [b.get("text", "") for b in c.get("buttons", [])],
                                 "indices": [], "examples": []})
        else:
            out["parts"].append({"component": (ctype or "other").lower(),
                                 "text": c.get("text", ""), "indices": [], "examples": []})
    return out


def _list_templates():
    r = sm.list_whatsapp_message_templates(id=_CFG["waba_id"])
    return {"templates": [{"name": t.get("templateName"), "status": t.get("templateStatus"),
                           "category": t.get("templateCategory"),
                           "language": t.get("templateLanguage"),
                           "metaTemplateId": t.get("metaTemplateId")}
                          for t in r.get("templates", [])]}


def _campaign_columns(meta_template_id=None):
    base = {"bucket": _CFG["campaign_bucket"], "phone": "phone"}
    if not meta_template_id:
        base.update({"columns": ["phone"], "legend": []})
        return base
    name, lang, cols, legend = lib.template_columns(sm, _CFG["waba_id"], meta_template_id)
    base.update({"name": name, "language": lang, "columns": cols, "legend": legend,
                 "objectType": lib.object_type_name(name), "folder": lib.s3_folder(name)})
    return base


def _send_one(body):
    to = (body.get("to") or "").strip()
    if not to.startswith("+"):
        to = "+" + to
    comps = []
    if body.get("header"):
        comps.append({"type": "header",
                      "parameters": [{"type": "text", "text": v} for v in body["header"]]})
    if body.get("bodyVars"):
        comps.append({"type": "body",
                      "parameters": [{"type": "text", "text": v} for v in body["bodyVars"]]})
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
               "type": "template",
               "template": {"name": body["name"],
                            "language": {"code": body.get("language", "pt_BR")},
                            "components": comps}}
    resp = sm.send_whatsapp_message(originationPhoneNumberId=_CFG["origin"],
                                    message=json.dumps(payload).encode("utf-8"),
                                    metaApiVersion=_CFG["meta_api"])
    return {"messageId": resp.get("messageId", ""), "ok": True}


def _campaign_send(csv_text, filename, meta_template_id, campaign_label=None):
    import csv as _csv
    import datetime
    import io
    bucket = _CFG["campaign_bucket"]
    if not bucket:
        return {"error": "campaign-bucket não configurado no SSM /atendimento/campaign-bucket"}
    if not meta_template_id:
        return {"error": "selecione o template da campanha"}
    name, lang, cols, legend = lib.template_columns(sm, _CFG["waba_id"], meta_template_id)
    lib.ensure_object_type(cp, name, cols, domain=_CFG["cp_domain"])
    lib.ensure_s3_folder(s3, bucket, name)
    otn = lib.object_type_name(name)
    folder = lib.s3_folder(name)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename or "campanha.csv")
    key = f"{folder}{stamp}-{safe}"
    s3.put_object(Bucket=bucket, Key=key, Body=csv_text.encode("utf-8"), ContentType="text/csv")
    rows = list(_csv.DictReader(io.StringIO(csv_text)))
    ok, errs, phones = 0, [], []
    for i, row in enumerate(rows, 1):
        phone = (row.get("phone") or row.get("Phone") or "").strip()
        if not phone:
            errs.append(f"linha {i}: sem phone")
            continue
        if not phone.startswith("+"):
            phone = "+" + phone
        obj = {"phone": phone}
        for k, v in row.items():
            if k and k.strip().lower() != "phone" and v and v.strip():
                obj[k.strip()] = v.strip()
        try:
            cp.put_profile_object(DomainName=_CFG["cp_domain"], ObjectTypeName=otn,
                                  Object=json.dumps(obj))
            ok += 1
            if phone not in phones:
                phones.append(phone)
        except Exception as e:  # noqa: BLE001
            errs.append(f"linha {i}: {e}")
    try:
        if phones:
            camp = lib.dispatch_campaign(sm, q, cc, connect, cp, name, meta_template_id, phones,
                                         label=(campaign_label or name), language=lang)
        else:
            camp = {"pending": True, "status": "SEM_TELEFONES"}
    except Exception as e:  # noqa: BLE001
        camp = {"error": str(e)}
    return {"ok": True, "template": name, "objectType": otn, "campaign": camp,
            "s3": f"s3://{bucket}/{key}", "gravados": ok, "destinatarios": len(phones),
            "total": len(rows), "erros": errs}


# --------------------------------------------------------------------------- router
def _resp(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def _subpath(event):
    raw = event.get("rawPath", "") or ""
    marker = "/atendimento/api/"
    if marker in raw:
        return raw.split(marker, 1)[1].strip("/")
    return raw.rsplit("/", 1)[-1].strip("/")


def _qs(event, key, default=""):
    return (event.get("queryStringParameters") or {}).get(key, default)


def handler(event, context):
    path = _subpath(event)
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method", "GET")
    if path == "health":
        return _resp(200, {"ok": True, "module": "atendimento",
                           "waba": _CFG["waba_id"], "bucket": bool(_CFG["campaign_bucket"])})

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except (ValueError, TypeError):
            body = {}
    try:
        if path == "templates":
            return _resp(200, _list_templates())
        if path == "template":
            mid = _qs(event, "metaTemplateId")
            if not mid:
                return _resp(400, {"error": "metaTemplateId obrigatório"})
            return _resp(200, _template_detail(mid))
        if path == "campaign/format":
            return _resp(200, _campaign_columns(_qs(event, "metaTemplateId") or None))
        if path == "send" and method == "POST":
            if not (body.get("to") or "").strip():
                return _resp(400, {"error": "telefone (to) obrigatório"})
            if not body.get("name"):
                return _resp(400, {"error": "selecione um template"})
            return _resp(200, _send_one(body))
        if path == "campaign/send" and method == "POST":
            return _resp(200, _campaign_send(body.get("csv", ""), body.get("filename", ""),
                                             body.get("metaTemplateId", ""),
                                             body.get("campaignName", "")))
        return _resp(404, {"error": f"rota não encontrada: {path}"})
    except Exception as e:  # noqa: BLE001
        print("atendimento error:", repr(e))
        return _resp(502, {"error": f"falha ao processar: {str(e)[:200]}"})
