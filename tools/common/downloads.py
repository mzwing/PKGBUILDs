from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.request import Request, urlopen

USER_AGENT = "PKGBUILDs-nvchecker-updater/1.0"


def fetch_bytes(url: str, *, user_agent: str = USER_AGENT) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request) as response:
        return response.read()


def fetch_json(url: str) -> Any:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def sha256_url(url: str) -> str:
    digest = hashlib.sha256()
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
