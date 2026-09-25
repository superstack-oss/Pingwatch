from __future__ import annotations

import base64
import json
from typing import Dict, Optional
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


def test_connection(config: Dict[str, str]) -> str:
    url = (config.get("servicenow_url") or "").rstrip("/")
    user = config.get("servicenow_user") or ""
    password = config.get("servicenow_password") or ""
    if not url or not user:
        return "ServiceNow URL and user are required"
    endpoint = url + "/api/now/table/incident?sysparm_limit=1"
    token = base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
    req = Request(endpoint, headers={"Authorization": "Basic " + token, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=8) as response:
            response.read()
        return "ok"
    except HTTPError as exc:
        return "ServiceNow HTTP %s" % exc.code
    except URLError as exc:
        return str(exc.reason or exc)


def create_incident(
    config: Dict[str, str],
    short_description: str,
    details: str,
    urgency: str = "2",
) -> Optional[str]:
    if str(config.get("servicenow_enabled") or "").lower() not in {"1", "true", "yes", "on"}:
        return None
    url = (config.get("servicenow_url") or "").rstrip("/")
    user = config.get("servicenow_user") or ""
    password = config.get("servicenow_password") or ""
    if not url or not user:
        return None
    endpoint = url + "/api/now/table/incident"
    token = base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
    payload = json.dumps(
        {
            "short_description": short_description,
            "description": details,
            "urgency": str(urgency or "2"),
            "impact": str(urgency or "2"),
        }
    ).encode("utf-8")
    req = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": "Basic " + token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
        return (body.get("result") or {}).get("sys_id")
    except Exception:
        return None
