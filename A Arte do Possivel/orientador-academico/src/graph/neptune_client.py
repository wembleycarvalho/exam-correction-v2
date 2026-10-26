"""Minimal Amazon Neptune openCypher client (SigV4-signed, stdlib only).

Neptune exposes an HTTPS openCypher endpoint at https://<endpoint>:8182/openCypher.
Requests are signed with SigV4 for service `neptune-db` when IAM auth is enabled.
Uses only botocore (already a boto3 dependency) + urllib to avoid extra packages,
which keeps the agent container and the loader script light.
"""
from __future__ import annotations

import json
import os
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


class NeptuneClient:
    def __init__(self, endpoint: str | None = None, port: int = 8182,
                 region: str | None = None, use_ssl: bool = True):
        self.endpoint = endpoint or os.environ["NEPTUNE_ENDPOINT"]
        self.port = int(os.environ.get("NEPTUNE_PORT", port))
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        scheme = "https" if use_ssl else "http"
        self.url = f"{scheme}://{self.endpoint}:{self.port}/openCypher"
        self._session = boto3.Session()

    def query(self, cypher: str, parameters: dict | None = None) -> list[dict]:
        """Run an openCypher query and return the list of result rows."""
        body = "query=" + urllib.parse.quote(cypher)
        if parameters:
            body += "&parameters=" + urllib.parse.quote(json.dumps(parameters))
        data = body.encode("utf-8")

        aws_req = AWSRequest(method="POST", url=self.url, data=data,
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
        creds = self._session.get_credentials().get_frozen_credentials()
        SigV4Auth(creds, "neptune-db", self.region).add_auth(aws_req)

        req = urllib.request.Request(self.url, data=data, method="POST")
        for k, v in aws_req.headers.items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("results", [])
