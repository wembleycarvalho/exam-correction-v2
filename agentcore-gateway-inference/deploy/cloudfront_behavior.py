"""Liga/desliga a rota /agentcore/* na distribution CloudFront do portal.

Aditivo e idempotente: clona a config de um behavior de módulo já existente (`/lms/*`),
preservando todos os demais behaviors.

Uso:
  python cloudfront_behavior.py --dist <DIST_ID> --api <API_DOMAIN>   # liga
  python cloudfront_behavior.py --dist <DIST_ID> --remove             # desliga (teardown)
"""
import argparse
import copy
import sys

import boto3

PATH = "/agentcore/*"
ORIGIN_ID = "agentcore-api"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--api", default="")
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    cf = boto3.client("cloudfront")
    r = cf.get_distribution_config(Id=args.dist)
    etag, cfg = r["ETag"], r["DistributionConfig"]
    behs = cfg["CacheBehaviors"]["Items"]
    origins = cfg["Origins"]["Items"]

    if args.remove:
        n0 = len(behs)
        cfg["CacheBehaviors"]["Items"] = [b for b in behs if b["PathPattern"] != PATH]
        cfg["Origins"]["Items"] = [o for o in origins if o["Id"] != ORIGIN_ID]
        cfg["CacheBehaviors"]["Quantity"] = len(cfg["CacheBehaviors"]["Items"])
        cfg["Origins"]["Quantity"] = len(cfg["Origins"]["Items"])
        if len(cfg["CacheBehaviors"]["Items"]) == n0:
            print("idempotente: nada a remover")
            return
        cf.update_distribution(Id=args.dist, IfMatch=etag, DistributionConfig=cfg)
        print("OK: behavior/origin do agentcore removidos")
        return

    if not args.api:
        sys.exit("--api é obrigatório para ligar")
    if any(b["PathPattern"] == PATH for b in behs):
        print("idempotente: behavior já existe")
        return

    lms = next(b for b in behs if b["PathPattern"] == "/lms/*")
    src = next(o for o in origins if o["Id"] == lms["TargetOriginId"])
    new_origin = copy.deepcopy(src)
    new_origin["Id"] = ORIGIN_ID
    new_origin["DomainName"] = args.api
    if "CustomHeaders" in new_origin:
        new_origin["CustomHeaders"] = {"Quantity": 0}
    origins.append(new_origin)
    cfg["Origins"]["Quantity"] = len(origins)

    new_beh = copy.deepcopy(lms)
    new_beh["PathPattern"] = PATH
    new_beh["TargetOriginId"] = ORIGIN_ID
    behs.append(new_beh)
    cfg["CacheBehaviors"]["Quantity"] = len(behs)

    cf.update_distribution(Id=args.dist, IfMatch=etag, DistributionConfig=cfg)
    print(f"OK: origin '{ORIGIN_ID}' + behavior {PATH} adicionados (behaviors={len(behs)})")


if __name__ == "__main__":
    main()
