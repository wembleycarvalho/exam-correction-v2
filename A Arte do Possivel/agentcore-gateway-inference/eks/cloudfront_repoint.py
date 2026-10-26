"""Repointa a origin `agentcore-api` da distribution CloudFront do portal para o ALB do
EKS (streaming SSE), no lugar da HTTP API. Idempotente.

O behavior /agentcore/* já existe (CachingDisabled + AllViewerExceptHostHeader, encaminha
Authorization). Aqui só trocamos a DomainName da origin para o ALB e o protocolo p/ http-only
(o listener do ALB é HTTP:80), e subimos o OriginReadTimeout p/ não cortar streams longos.

Uso:
  python cloudfront_repoint.py --dist <DIST_ID> --alb <ALB_DNS>
  python cloudfront_repoint.py --dist <DIST_ID> --restore <API_DOMAIN>   # volta p/ HTTP API
"""
import argparse
import sys

import boto3

ORIGIN_ID = "agentcore-api"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--alb", default="")
    ap.add_argument("--restore", default="")
    args = ap.parse_args()

    target = args.restore or args.alb
    if not target:
        sys.exit("informe --alb <dns> (ou --restore <api-domain>)")
    protocol = "https-only" if args.restore else "http-only"

    cf = boto3.client("cloudfront")
    r = cf.get_distribution_config(Id=args.dist)
    etag, cfg = r["ETag"], r["DistributionConfig"]
    origins = cfg["Origins"]["Items"]
    o = next((x for x in origins if x["Id"] == ORIGIN_ID), None)
    if o is None:
        sys.exit(f"origin '{ORIGIN_ID}' não encontrada (rode o cloudfront_behavior.py primeiro)")

    if o.get("DomainName") == target and \
       o.get("CustomOriginConfig", {}).get("OriginProtocolPolicy") == protocol:
        print("idempotente: origin já aponta para o alvo")
        return

    o["DomainName"] = target
    coc = o.setdefault("CustomOriginConfig", {})
    coc["OriginProtocolPolicy"] = protocol
    coc.setdefault("HTTPPort", 80)
    coc.setdefault("HTTPSPort", 443)
    coc["OriginReadTimeout"] = 60          # máx permitido; folga p/ SSE
    coc["OriginKeepaliveTimeout"] = 60
    coc.setdefault("OriginSslProtocols", {"Quantity": 1, "Items": ["TLSv1.2"]})

    cf.update_distribution(Id=args.dist, IfMatch=etag, DistributionConfig=cfg)
    print(f"OK: origin '{ORIGIN_ID}' -> {target} ({protocol}, readTimeout=60)")


if __name__ == "__main__":
    main()
