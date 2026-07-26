"""Minimal Azure OpenAI Responses API client for the proposal workflow."""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def is_configured() -> bool:
    return bool(_base_url() and _api_key())


def create_json_response(prompt: str, use_web_search: bool = False) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """Run the deployed model and return parsed JSON plus URL citations."""
    if not is_configured():
        raise RuntimeError(
            "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT, "
            "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT_NAME."
        )

    payload: Dict[str, Any] = {
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-mini"),
        "input": prompt,
    }
    if use_web_search:
        payload["tools"] = [{"type": "web_search"}]
    else:
        payload["text"] = {"format": {"type": "json_object"}}

    request = urllib.request.Request(
        f"{_base_url()}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": _api_key(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Azure OpenAI request failed ({exc.code}): {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure OpenAI request could not be reached: {exc.reason}") from exc

    response_text = _response_text(raw_response)
    if not response_text:
        raise RuntimeError("Azure OpenAI returned no text response.")

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Azure OpenAI did not return valid JSON.") from exc
    citations = _citations(raw_response) or _citations_from_json(parsed)
    return parsed, citations


def _base_url() -> str:
    """Support a Foundry Project endpoint or the standard Azure OpenAI endpoint."""
    project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
    if project_endpoint:
        return f"{project_endpoint}/openai/v1"

    configured = os.getenv("AZURE_OPENAI_RESPONSES_ENDPOINT", "").strip().rstrip("/")
    if configured:
        return configured

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    if not endpoint:
        return ""
    return endpoint if endpoint.endswith("/openai/v1") else f"{endpoint}/openai/v1"


def _api_key() -> str:
    return (
        os.getenv("FOUNDRY_API_KEY", "").strip()
        or os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    )


def _response_text(response: Dict[str, Any]) -> str:
    if response.get("output_text"):
        return str(response["output_text"])

    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                return str(content["text"])
    return ""


def _citations(response: Dict[str, Any]) -> List[Dict[str, str]]:
    citations: List[Dict[str, str]] = []
    seen_urls = set()
    for item in response.get("output", []):
        for content in item.get("content", []):
            for annotation in content.get("annotations", []):
                citation = annotation.get("url_citation", {})
                url = citation.get("url", "")
                if url and url not in seen_urls:
                    citations.append({"title": citation.get("title", url), "url": url})
                    seen_urls.add(url)
    return citations


def _citations_from_json(value: Any) -> List[Dict[str, str]]:
    """Recover inline URLs when a tool response is returned in JSON text mode."""
    urls: List[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            urls.extend(re.findall(r"https?://[^\s)\]}>,]+", item))

    visit(value)
    unique_urls = list(dict.fromkeys(urls))
    return [{"title": url, "url": url} for url in unique_urls]
