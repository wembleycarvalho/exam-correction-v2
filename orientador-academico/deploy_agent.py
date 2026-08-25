#!/usr/bin/env python3
"""Implanta o agente Orientador no AgentCore Runtime com VPC (o toolkit instalado não
suporta VPC). Build ARM64 (Dockerfile) -> push ECR -> create/update_agent_runtime
(container + VPC + role + env) -> publica ARN no SSM -> carrega o Neptune (action=load).

Uso (a partir de orientador-academico/, com Docker/Colima ativo e credenciais AWS):
  AWS_REGION=us-east-1 STACK_NAME=exam-correction-v2 .venv/bin/python deploy_agent.py
"""
import base64
import json
import os
import subprocess
import sys
import time
import uuid

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
STACK = os.environ.get("STACK_NAME", "exam-correction-v2")
NAME = "orientador_agent"
REPO = "orientador-agent"


def sh(cmd, **kw):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


def main():
    cf = boto3.client("cloudformation", region_name=REGION)
    outs = {o["OutputKey"]: o["OutputValue"]
            for o in cf.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]}
    neptune = outs["OrientadorNeptuneEndpoint"]
    all_subnets = outs["OrientadorSubnets"].split(",")
    sg = outs["OrientadorAgentSg"]

    # AgentCore Runtime só suporta certas AZs em us-east-1 (as demais dão CREATE_FAILED).
    # Além disso, em networkMode=VPC o próprio runtime precisa baixar a imagem do ECR e
    # falar com Bedrock/CloudWatch: isso exige EGRESS. Subnets públicas da VPC default não
    # servem (a ENI do AgentCore não recebe IP público), então escolhemos subnets PRIVADAS
    # com rota 0.0.0.0/0 para um NAT gateway (que a VPC já possui), em AZ suportada.
    supported_az = set((os.environ.get("AGENTCORE_SUPPORTED_AZ")
                        or "use1-az1,use1-az2,use1-az4").split(","))
    ec2 = boto3.client("ec2", region_name=REGION)
    override = os.environ.get("AGENTCORE_SUBNETS")
    if override:
        subnets = override.split(",")
        print(f"Subnets (override): {subnets}")
    else:
        vpc_id = ec2.describe_subnets(SubnetIds=all_subnets[:1])["Subnets"][0]["VpcId"]
        subnets = _egress_subnets_in_supported_az(ec2, vpc_id, supported_az)
        if not subnets:
            # fallback: qualquer subnet informada pela stack em AZ suportada
            desc = ec2.describe_subnets(SubnetIds=all_subnets)["Subnets"]
            subnets = [s["SubnetId"] for s in desc if s.get("AvailabilityZoneId") in supported_az]
        if not subnets:
            raise SystemExit("Nenhuma subnet com egress (NAT) em AZ suportada pelo AgentCore.")
        print(f"Subnets (privadas c/ NAT, AZ suportada): {subnets}")
    role = outs["OrientadorRuntimeRoleArn"]
    param = outs["OrientadorRuntimeArnParam"]
    model = outs.get("OrientadorModelId", "amazon.nova-pro-v1:0")
    acct = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    registry = f"{acct}.dkr.ecr.{REGION}.amazonaws.com"
    # Tag única por deploy: o AgentCore Runtime não re-baixa a imagem quando o update
    # aponta para a MESMA tag (:latest); usar uma tag nova por deploy garante o pull.
    tag = "v" + str(int(time.time()))
    uri = f"{registry}/{REPO}:{tag}"
    latest = f"{registry}/{REPO}:latest"

    # 1) ECR repo
    ecr = boto3.client("ecr", region_name=REGION)
    try:
        ecr.create_repository(repositoryName=REPO)
        print("ECR repo criado:", REPO)
    except ecr.exceptions.RepositoryAlreadyExistsException:
        print("ECR repo já existe:", REPO)

    # 2) docker login + build ARM64 + push
    pw = subprocess.check_output(["aws", "ecr", "get-login-password", "--region", REGION])
    sh(["docker", "login", "--username", "AWS", "--password-stdin", registry], input=pw)
    # --provenance=false --sbom=false: sem esses flags o buildx publica um OCI image
    # INDEX (manifest list) com uma entrada de atestação unknown/unknown. O AgentCore
    # Runtime não resolve esse índice e o container nunca inicia (502 sem logs).
    # Precisamos de uma imagem single-platform (arm64) pura. Usamos buildx com
    # --load para gravar no docker local e depois push.
    sh(["docker", "buildx", "build", "--platform", "linux/arm64",
        "--provenance=false", "--sbom=false", "--load",
        "-f", "agent/Dockerfile", "-t", uri, "-t", latest, "."])
    sh(["docker", "push", uri])
    sh(["docker", "push", latest])

    # 3) create/update agent runtime (container + VPC + role + env)
    ctl = boto3.client("bedrock-agentcore-control", region_name=REGION)
    artifact = {"containerConfiguration": {"containerUri": uri}}
    network = {"networkMode": "VPC",
               "networkModeConfig": {"securityGroups": [sg], "subnets": subnets}}
    proto = {"serverProtocol": "HTTP"}
    env = {"NEPTUNE_ENDPOINT": neptune, "ORIENTADOR_MODEL_ID": model, "AWS_REGION": REGION}

    # list_agent_runtimes é eventualmente consistente: pode devolver um runtime já
    # deletado (fantasma). Confirmamos cada candidato com get_agent_runtime e só o
    # tratamos como existente se estiver realmente presente e num estado utilizável.
    existing_id = None
    for r in ctl.list_agent_runtimes().get("agentRuntimes", []):
        if r.get("agentRuntimeName") != NAME:
            continue
        rid = r.get("agentRuntimeId")
        try:
            st = str(ctl.get_agent_runtime(agentRuntimeId=rid).get("status", ""))
        except Exception:
            st = "GONE"
        print(f"Runtime candidato {rid}: status={st}")
        if st in ("GONE", "") or "DELET" in st.upper():
            continue  # fantasma/deletando -> ignora
        if "FAIL" in st.upper():
            print(f"Removendo runtime anterior com falha ({rid})…")
            with suppress_all():
                ctl.delete_agent_runtime(agentRuntimeId=rid)
            _wait_gone(ctl, rid)
            continue
        existing_id = rid
        break
    if existing_id:
        print("Atualizando runtime existente:", existing_id)
        resp = ctl.update_agent_runtime(
            agentRuntimeId=existing_id, agentRuntimeArtifact=artifact, roleArn=role,
            networkConfiguration=network, protocolConfiguration=proto, environmentVariables=env)
        arn = resp.get("agentRuntimeArn") or _arn_by_id(ctl, existing_id)
    else:
        print("Criando runtime…")
        resp = ctl.create_agent_runtime(
            agentRuntimeName=NAME, agentRuntimeArtifact=artifact, roleArn=role,
            networkConfiguration=network, protocolConfiguration=proto,
            environmentVariables=env, clientToken="orientador-" + uuid.uuid4().hex)
        arn = resp["agentRuntimeArn"]
    print("Runtime ARN:", arn)

    # 4) aguarda ficar pronto (best-effort)
    for _ in range(40):
        try:
            st = ctl.get_agent_runtime(agentRuntimeId=existing_id or arn.split("/")[-1]).get("status")
        except Exception:
            st = "?"
        print("  status:", st)
        if st in ("READY", "ACTIVE"):
            break
        if isinstance(st, str) and "FAIL" in st.upper():
            raise SystemExit("Runtime falhou: " + st)
        time.sleep(15)

    # 5) publica no SSM
    boto3.client("ssm", region_name=REGION).put_parameter(
        Name=param, Value=arn, Type="String", Overwrite=True)
    print("SSM publicado:", param)

    # 6) carrega o Neptune (de dentro da VPC, pelo agente). Cold start pode demorar; retry.
    # Pule com AGENT_SKIP_LOAD=1 em deploys só de código (para não apagar dados mutáveis:
    # pedidos de transferência, mudanças de alvo/curso já feitas).
    if os.environ.get("AGENT_SKIP_LOAD") == "1":
        print("AGENT_SKIP_LOAD=1 — pulando a recarga do Neptune (preserva dados mutáveis).")
        return
    print("Carregando o grafo no Neptune (action=load)…")
    ac = boto3.client("bedrock-agentcore", region_name=REGION)
    last = None
    for attempt in range(1, 6):
        try:
            out = ac.invoke_agent_runtime(
                agentRuntimeArn=arn, runtimeSessionId="load" + uuid.uuid4().hex,
                contentType="application/json", accept="application/json",
                payload=json.dumps({"action": "load", "clear": True}).encode())
            body = out["response"].read() if hasattr(out.get("response"), "read") else out.get("response")
            print("Resposta da carga:", body)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  tentativa {attempt} falhou: {e}; aguardando 20s…")
            time.sleep(20)
    print("Carga não concluída após retries:", last)


from contextlib import contextmanager


@contextmanager
def suppress_all():
    try:
        yield
    except Exception as e:  # noqa: BLE001
        print("  (ignorado)", e)


def _wait_gone(ctl, rid, tries=25, delay=6):
    """Espera um runtime sumir de verdade (get_agent_runtime falha)."""
    for _ in range(tries):
        try:
            st = ctl.get_agent_runtime(agentRuntimeId=rid).get("status", "?")
            print("  aguardando remoção, status:", st)
        except Exception:
            print("  runtime removido:", rid)
            return
        time.sleep(delay)


def _egress_subnets_in_supported_az(ec2, vpc_id, supported_az):
    """Subnets da VPC que têm rota default para um NAT gateway (egress) e estão em AZ
    suportada pelo AgentCore. Resolve a route table explícita da subnet ou a main."""
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    rts = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["RouteTables"]
    explicit = {}  # subnet_id -> routes
    main_routes = None
    for rt in rts:
        is_main = any(a.get("Main") for a in rt.get("Associations", []))
        if is_main:
            main_routes = rt.get("Routes", [])
        for a in rt.get("Associations", []):
            if a.get("SubnetId"):
                explicit[a["SubnetId"]] = rt.get("Routes", [])

    def has_nat_egress(sid):
        routes = explicit.get(sid, main_routes or [])
        return any(r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("NatGatewayId")
                   for r in routes)

    out = [s["SubnetId"] for s in subnets
           if s.get("AvailabilityZoneId") in supported_az and has_nat_egress(s["SubnetId"])]
    return out


def _arn_by_id(ctl, rid):
    for r in ctl.list_agent_runtimes().get("agentRuntimes", []):
        if r.get("agentRuntimeId") == rid:
            return r.get("agentRuntimeArn")
    return None


if __name__ == "__main__":
    sys.exit(main())
