"""Liga/desliga as rotas do módulo Atendimento na distribution CloudFront do portal.

Aditivo e idempotente. Clona a config de um behavior existente (`/lms/*`) preservando o resto.
  - /atendimento/*        -> HTTP API (templates/campanhas, Fase 1)          [origin atendimento-api]
  - /atendimento/api/ask  -> Function URL do bridge (SSE streaming, Fase 2)  [origin atendimento-stream]
O behavior de streaming é inserido ANTES de /atendimento/* (CloudFront casa na ordem da lista).

Uso:
  python cloudfront_behavior.py --dist <ID> --api <API_DOMAIN> [--stream <FURL_DOMAIN>]
  python cloudfront_behavior.py --dist <ID> --remove
"""
import argparse
import copy
import sys

import boto3

PATH = "/atendimento/*"
ORIGIN_ID = "atendimento-api"
STREAM_PATH = "/atendimento/api/ask"
STREAM_ORIGIN_ID = "atendimento-stream"


def _clone_origin(origins, src_id, new_id, domain, protocol):
    src = next(o for o in origins if o["Id"] == src_id)
    o = copy.deepcopy(src)
    o["Id"] = new_id
    o["DomainName"] = domain
    if "CustomHeaders" in o:
        o["CustomHeaders"] = {"Quantity": 0}
    coc = o.setdefault("CustomOriginConfig", {"HTTPPort": 80, "HTTPSPort": 443,
                                              "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]}})
    coc["OriginProtocolPolicy"] = protocol
    coc["OriginReadTimeout"] = 60          # folga p/ streaming
    coc["OriginKeepaliveTimeout"] = 60
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--api", default="")
    ap.add_argument("--stream", default="")
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    cf = boto3.client("cloudfront")
    r = cf.get_distribution_config(Id=args.dist)
    etag, cfg = r["ETag"], r["DistributionConfig"]
    behs = cfg["CacheBehaviors"]["Items"]
    origins = cfg["Origins"]["Items"]

    if args.remove:
        before = len(behs)
        cfg["CacheBehaviors"]["Items"] = [b for b in behs if b["PathPattern"] not in (PATH, STREAM_PATH)]
        cfg["Origins"]["Items"] = [o for o in origins if o["Id"] not in (ORIGIN_ID, STREAM_ORIGIN_ID)]
        cfg["CacheBehaviors"]["Quantity"] = len(cfg["CacheBehaviors"]["Items"])
        cfg["Origins"]["Quantity"] = len(cfg["Origins"]["Items"])
        if len(cfg["CacheBehaviors"]["Items"]) == before:
            print("idempotente: nada a remover")
            return
        cf.update_distribution(Id=args.dist, IfMatch=etag, DistributionConfig=cfg)
        print("OK: behaviors/origins do atendimento removidos")
        return

    if not args.api:
        sys.exit("--api é obrigatório para ligar")
    lms = next(b for b in behs if b["PathPattern"] == "/lms/*")

    # 1) origin + behavior /atendimento/* (HTTP API) — idempotente
    if not any(b["PathPattern"] == PATH for b in behs):
        origins.append(_clone_origin(origins, lms["TargetOriginId"], ORIGIN_ID, args.api, "https-only"))
        nb = copy.deepcopy(lms); nb["PathPattern"] = PATH; nb["TargetOriginId"] = ORIGIN_ID
        behs.append(nb)
        print(f"+ behavior {PATH} -> {ORIGIN_ID}")
    else:
        print(f"idempotente: {PATH} já existe")

    # 2) origin + behavior /atendimento/api/ask (Function URL, streaming) — ANTES de /atendimento/*
    if args.stream:
        if not any(o["Id"] == STREAM_ORIGIN_ID for o in origins):
            origins.append(_clone_origin(origins, lms["TargetOriginId"], STREAM_ORIGIN_ID, args.stream, "https-only"))
        if not any(b["PathPattern"] == STREAM_PATH for b in behs):
            sb = copy.deepcopy(lms); sb["PathPattern"] = STREAM_PATH; sb["TargetOriginId"] = STREAM_ORIGIN_ID
            # insere antes do /atendimento/* (ordem = precedência no CloudFront)
            idx = next((i for i, b in enumerate(behs) if b["PathPattern"] == PATH), len(behs))
            behs.insert(idx, sb)
            print(f"+ behavior {STREAM_PATH} -> {STREAM_ORIGIN_ID} (streaming, antes de {PATH})")
        else:
            print(f"idempotente: {STREAM_PATH} já existe")

    cfg["Origins"]["Quantity"] = len(origins)
    cfg["CacheBehaviors"]["Quantity"] = len(behs)
    cf.update_distribution(Id=args.dist, IfMatch=etag, DistributionConfig=cfg)
    print(f"OK: behaviors atualizados (total={len(behs)})")


if __name__ == "__main__":
    main()
