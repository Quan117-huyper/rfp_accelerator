# Runbook
## Local Run

```powershell
python backend/proposal_app.py
```

```powershell
cd front-end
npm install
npm start
```

## Environment Variables

```env
GEMINI_API_KEY="your-key"

For the Azure-backed proposal research workflow, prefer:

AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
AZURE_OPENAI_API_KEY="your-key"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5-mini"

The optional AZURE_OPENAI_RESPONSES_ENDPOINT value is the full v1 base URL when
the Foundry project provides a different endpoint:

AZURE_OPENAI_RESPONSES_ENDPOINT="https://your-resource.openai.azure.com/openai/v1"
GEMINI_MODEL="gemini-2.5-flash"
```

## Azure Foundry and Key Vault

For the Azure-backed flow, add only non-secret endpoints to the local `.env`:

```env
FOUNDRY_PROJECT_ENDPOINT="https://your-project.services.ai.azure.com/api/projects/your-project"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5-mini"
AZURE_KEY_VAULT_URI="https://your-vault-name.vault.azure.net/"
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://your-resource.cognitiveservices.azure.com/"
AZURE_SEARCH_ENDPOINT="https://your-search.search.windows.net"
```

The backend retrieves these Key Vault secrets at startup: `foundry`,
`azure-open-api`, `azure-search-api`, and `Document-intel-key`.

For local development without Azure CLI, set the following temporarily and start
the backend from the same terminal. Azure prints a device-code sign-in prompt;
complete it at the Microsoft URL before making API calls.

```powershell
$env:AZURE_USE_DEVICE_CODE = "true"
python backend/proposal_app.py
```

On the VM, leave `AZURE_USE_DEVICE_CODE` unset and assign the VM managed identity
the `Key Vault Secrets User` role instead.

## Template Setup

- Put enterprise PPTX templates under `templates/<template_id>/template.pptx`
- Keep placeholder names consistent with the renderer
- Use `templates/template_registry.json` to register templates

## Checkpoints

- Backend health: `/health`
- Proposal analyze: `/proposal/analyze`
- Proposal upload: `/proposal/upload`
- PPT export: `/proposal/export-pptx`
- Azure configuration: `/health` reports endpoint and Key Vault status without
  exposing any secret values.
