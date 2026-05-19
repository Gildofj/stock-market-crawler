#!/usr/bin/env python3
"""Fetch a secret from Google Secret Manager using the GCE metadata server.

Used by [scripts/worker_entrypoint.sh](scripts/worker_entrypoint.sh) on the
Compute Engine worker VM. The container image is Python-based and may not ship
with `curl`, so we use stdlib `urllib` to avoid adding a system dependency.

Usage:
    GCP_PROJECT=my-project python3 scripts/fetch_secret.py <secret-name>
"""

import base64
import json
import os
import sys
import urllib.request

METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)


def fetch(name: str) -> str:
    token_req = urllib.request.Request(
        METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"}
    )
    with urllib.request.urlopen(token_req, timeout=5) as resp:
        token = json.loads(resp.read())["access_token"]

    project = os.environ["GCP_PROJECT"]
    secret_url = (
        f"https://secretmanager.googleapis.com/v1/projects/{project}"
        f"/secrets/{name}/versions/latest:access"
    )
    secret_req = urllib.request.Request(
        secret_url, headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(secret_req, timeout=10) as resp:
        payload = json.loads(resp.read())["payload"]["data"]
    return base64.b64decode(payload).decode()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: fetch_secret.py <secret-name>", file=sys.stderr)
        sys.exit(2)
    sys.stdout.write(fetch(sys.argv[1]))
