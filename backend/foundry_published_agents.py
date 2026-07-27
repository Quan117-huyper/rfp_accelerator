"""Invoke published Foundry prompt agents through their Responses endpoints."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict

from azure_runtime import credential_for_runtime


ENDPOINTS = {
    "requirement": "FOUNDRY_REQUIREMENT_AGENT_ENDPOINT",
    "architect": "FOUNDRY_ARCHITECT_AGENT_ENDPOINT",
    "proposal": "FOUNDRY_PROPOSAL_AGENT_ENDPOINT",
}
TOKEN_SCOPE = "https://ai.azure.com/.default"


def is_configured(agent_kind: str) -> bool:
    return bool(os.getenv(ENDPOINTS[agent_kind], "").strip())


def invoke(agent_kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = os.getenv(ENDPOINTS[agent_kind], "").strip()
    if not endpoint:
        raise RuntimeError(f"Published {agent_kind} agent endpoint is not configured.")

    parsed_url = urllib.parse.urlparse(endpoint)
    query = urllib.parse.parse_qs(parsed_url.query)
    query.setdefault("api-version", ["v1"])
    endpoint = urllib.parse.urlunparse(parsed_url._replace(query=urllib.parse.urlencode(query, doseq=True)))
    token = credential_for_runtime().get_token(TOKEN_SCOPE).token
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"input": json.dumps(payload, ensure_ascii=False), "stream": False}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Published {agent_kind} agent failed ({exc.code}): {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Published {agent_kind} agent could not be reached: {exc.reason}") from exc

    text = _response_text(body)
    if not text:
        raise RuntimeError(f"Published {agent_kind} agent returned no text response.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Published {agent_kind} agent did not return valid JSON.") from exc


def _response_text(body: Dict[str, Any]) -> str:
    if body.get("output_text"):
        return str(body["output_text"])
    for item in body.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                text = content["text"]
                return str(text.get("value") if isinstance(text, dict) else text)
    return ""
