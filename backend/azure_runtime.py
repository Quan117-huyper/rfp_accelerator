"""Resolve Azure configuration from local environment variables or Key Vault."""

import os
from pathlib import Path
from typing import Dict


SECRET_NAMES: Dict[str, str] = {
    "FOUNDRY_API_KEY": "foundry",
    "AZURE_OPENAI_API_KEY": "azure-open-api",
    "AZURE_SEARCH_KEY": "azure-search-api",
    "AZURE_DOCUMENT_INTELLIGENCE_KEY": "Document-intel-key",
}


def _truthy_environment(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _credential_for_runtime():
    """Use browser sign-in only when a local developer explicitly opts in.

    Deployed workloads continue to use DefaultAzureCredential so the VM can use a
    managed identity with no browser dependency.
    """
    from azure.identity import DefaultAzureCredential, DeviceCodeCredential, InteractiveBrowserCredential

    if _truthy_environment("AZURE_USE_DEVICE_CODE"):
        return DeviceCodeCredential(
            additionally_allowed_tenants=["*"],
            prompt_callback=lambda verification_uri, user_code, expires_on: print(
                f"Azure sign-in: open {verification_uri} and enter code {user_code} before {expires_on}.",
                flush=True,
            ),
        )
    if _truthy_environment("AZURE_USE_INTERACTIVE_BROWSER"):
        # Student subscriptions can expose the Vault through a tenant different
        # from the browser credential's home tenant.
        return InteractiveBrowserCredential(additionally_allowed_tenants=["*"])
    return DefaultAzureCredential()


def load_azure_runtime_configuration() -> Dict[str, str]:
    """Populate missing Azure secrets from Key Vault without logging secret values.

    Local development can keep using .env. On the VM, DefaultAzureCredential uses
    the VM's managed identity once it has the Key Vault Secrets User role.
    """
    vault_url = os.getenv("AZURE_KEY_VAULT_URI", "").strip()
    resolved = {"source": "environment", "key_vault": "not_configured"}
    if not vault_url:
        _set_legacy_document_intelligence_name()
        return resolved

    try:
        _ensure_azure_cli_on_path()
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=vault_url, credential=_credential_for_runtime())
        fetched = 0
        for environment_name, secret_name in SECRET_NAMES.items():
            if os.getenv(environment_name):
                continue
            os.environ[environment_name] = client.get_secret(secret_name).value
            fetched += 1
        if os.getenv("FOUNDRY_API_KEY") and not os.getenv("AZURE_OPENAI_API_KEY"):
            os.environ["AZURE_OPENAI_API_KEY"] = os.environ["FOUNDRY_API_KEY"]
        resolved = {"source": "key_vault" if fetched else "environment", "key_vault": "connected"}
    except Exception as exc:
        # A developer machine may not have an Azure CLI session. Existing .env
        # values still allow the local demo to run in that situation.
        resolved = {
            "source": "environment",
            "key_vault": "unavailable",
            "diagnostic": type(exc).__name__,
        }

    _set_legacy_document_intelligence_name()
    return resolved


def _set_legacy_document_intelligence_name() -> None:
    """Keep the legacy modules compatible with the new descriptive variable."""
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    if key and not os.getenv("FORM_RECOGNIZER_KEY"):
        os.environ["FORM_RECOGNIZER_KEY"] = key


def _ensure_azure_cli_on_path() -> None:
    """Make a fresh Windows Azure CLI installation visible to AzureCliCredential."""
    cli_directory = Path(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin")
    if cli_directory.exists() and str(cli_directory) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{cli_directory}{os.pathsep}{os.environ.get('PATH', '')}"
