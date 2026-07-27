# Runbook

## Local Run

Run all commands from the project root:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
```

Start the proposal backend:

```powershell
.\venv\Scripts\python.exe backend\proposal_app.py --port 5000
```

Start the React frontend in a second terminal:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3\front-end"
npm install
npm start
```

If `node_modules` already exists, `npm install` can be skipped.

Open:

```text
http://localhost:3000
```

Backend health check:

```powershell
Invoke-RestMethod http://localhost:5000/health
```

If Azure authentication is required locally:

```powershell
az login
```

If browser login is not available, use device-code login:

```powershell
$env:AZURE_USE_DEVICE_CODE = "true"
.\venv\Scripts\python.exe backend\proposal_app.py --port 5000
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

Current master template:

```text
templates/master_template/template.pptx
```

If the master template download opens with a PowerPoint error, regenerate the
valid local demo master template:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
.\venv\Scripts\python.exe scripts\create_valid_master_template.py
```

Current local renderer template id:

```text
master_template
```

Important: `master_template` is registered in this project renderer, not inside
the upstream PPTAgent template registry. DeepPresenter/PPTAgent currently sees
only its own template names such as `thu`, `default`, `cip`, `ucas`, `beamer`,
and `hit`.

## Full E2E Test Case

This test runs from input DOCX through the real published agents, answers HITL,
then exports a PPTX using the local `master_template` renderer.

Create or refresh the realistic DOCX fixture:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
.\venv\Scripts\python.exe scripts\create_e2e_rfp_fixture.py
```

Create or refresh OCR/layout PDF fixtures:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
.\venv\Scripts\python.exe scripts\create_ocr_pdf_fixtures.py
```

Run the full E2E workflow:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
$env:E2E_TEMPLATE_ID = "master_template"
.\venv\Scripts\python.exe scripts\run_real_agent_e2e.py
```

Architecture research modes exposed in the frontend:

```text
azure_official_only   Azure official docs plus Microsoft/Azure GitHub sources
azure_github_papers   Azure official docs plus Microsoft/Azure GitHub plus public papers
off                   No public web research
```

The requirement HITL popup includes `Add web search + GitHub/papers to Architect
prompt`. When enabled, the resume payload sets `research_mode` to
`azure_github_papers` and appends a safe evidence instruction for the Architect
Agent. The Architecture page then displays returned sources with source-type
badges such as `azure_docs`, `microsoft_github`, and `research_paper`.

The backend sends only safe technical queries to web search. It does not send
customer document text, customer names, private URLs, credentials, or internal
identifiers to public search.

Expected successful summary shape:

```json
{
  "template_id": "master_template",
  "requirement_runtime": "foundry_published_requirement_agent",
  "requirement_answered_questions": 3,
  "architect_runtime": "foundry_published_architect_agent",
  "proposal_runtime": "foundry_published_proposal_agent",
  "pptx_export": {
    "template_id": "master_template",
    "filename": "proposal_master_template_<proposal_id>.pptx"
  }
}
```

Main outputs:

```text
generated/test-fixtures/contoso_proposal_automation_rfp.docx
generated/test-fixtures/scanned_rfp_ocr_case.pdf
generated/test-fixtures/table_heavy_layout_case.pdf
generated/e2e-results/00_e2e_summary.json
generated/e2e-results/01_requirement_agent_output.json
generated/e2e-results/01_requirement_hitl.json
generated/e2e-results/02_requirement_hitl_answer.json
generated/e2e-results/03_architect_agent_output.json
generated/e2e-results/05_proposal_agent_output.json
generated/e2e-results/06_pptagent_slide_plan.json
generated/e2e-results/07_pptx_export.json
generated/proposal_master_template_<proposal_id>.pptx
```

The HITL answer script reads every Requirement Agent question and writes answers
to `02_requirement_hitl_answer.json`. Current realistic answers include:

- Retention conflict: choose 90 days and treat 30 days as superseded.
- Availability: use 99.5% during Vietnam business hours, RPO 24 hours, RTO 4 hours.
- Architect instruction: keep customer document content out of public web search and prefer a low-cost Azure POC with production upgrade path.

## Run Tests

Backend tests:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
.\venv\Scripts\python.exe -m unittest backend.tests.test_proposal_pipeline -v
```

Expected:

```text
Ran 21 tests
OK
```

OCR-specific test coverage:

```text
test_image_only_pdf_uses_document_intelligence_ocr
test_table_heavy_pdf_uses_document_intelligence_layout
```

Architecture research policy test coverage:

```text
test_architect_research_policy_allows_github_and_papers
test_azure_official_research_filters_non_official_sources
```

## Long Document Requirement Extraction Logic

Implemented in `backend/proposal_ingestion.py`:

```python
WHOLE_DOCUMENT_LIMIT_TOKENS = 40_000
CHUNK_TARGET_TOKENS = 32_000
CHUNK_MAX_TOKENS = 40_000
CHUNK_OVERLAP_TOKENS = 300
```

Mode selection:

```text
Parse DOCX/PDF/text with metadata
-> for PDF pages, inspect native text quality and layout risk
-> use Document Intelligence when page is scan/image-heavy/layout-heavy/garbled
-> estimate tokens
-> if <= 40k: create one Whole Document chunk
-> if > 40k: split by heading/section boundaries
-> pack adjacent small sections into one chunk near the budget
-> split inside a section only when that section alone exceeds max token budget
```

Requirement Agent orchestration:

```text
whole_document: one Requirement Agent call
chunked: one Requirement Agent call per chunk/section pack
all outputs -> global normalize -> deduplicate -> conflict questions <= 3
```

Cross-chunk conflict detection currently covers practical cases such as:

```text
delete after 30 days vs retain at least 90 days
availability mentioned but left TBD/to be confirmed
```

## DeepPresenter / PPTAgent Status

Prepare input from the previous Proposal Agent output:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
@'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))
from deep_presenter_renderer import proposal_to_pptagent_input
checkpoint = json.loads(Path("generated/e2e-results/05_proposal_checkpoint.json").read_text(encoding="utf-8"))
payload = proposal_to_pptagent_input(checkpoint["state"]["proposal"], "master_template")
Path("generated/e2e-results/08_deeppresenter_pptagent_input.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(payload["pptagent_input"]["deck_title"])
print(len(payload["pptagent_input"]["slides"]))
'@ | .\venv\Scripts\python.exe -
```

Run DeepPresenter with Foundry-compatible profile:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
$env:DEEPPRESENTER_PROFILE = "foundry_compat"
.\venv\Scripts\python.exe -c "import json, os, sys; from pathlib import Path; sys.path.insert(0, str(Path('backend').resolve())); from deep_presenter_renderer import render_with_deep_presenter; proposal=json.loads(Path('generated/e2e-results/05_proposal_checkpoint.json').read_text(encoding='utf-8'))['state']['proposal']; print(render_with_deep_presenter(proposal, 'master_template'))"
```

Current observed status:

```text
DeepPresenter container: running
Foundry-compatible profile: connects
PPTAgent MCP: connects
Input source: published Proposal Agent pptagent_input
Final PPTX: not emitted
```

Current blocker:

```text
The upstream PPTAgent template registry does not include this project's
master_template id. PPTAgent reports available templates: thu, default, cip,
ucas, beamer, hit. The model then asks for template confirmation instead of
calling slide-generation tools.
```

Saved diagnostics:

```text
generated/e2e-results/08_deeppresenter_pptagent_input.json
generated/e2e-results/09_deeppresenter_export.json
generated/e2e-results/09_deeppresenter_status_summary.json
modules/PPTAgent/workspace/<run-id>/.history/deeppresenter-loop.log
```

Cleanup any stuck DeepPresenter run:

```powershell
docker exec deeppresenter-host pkill -f /opt/workspace/run_deep_presenter_stack.py
```

## Checkpoints

- Backend health: `/health`
- Proposal analyze: `/proposal/analyze`
- Proposal upload: `/proposal/upload`
- HITL start upload: `/proposal/hitl/start-upload`
- HITL resume: `/proposal/hitl/<thread_id>/resume`
- PPT export: `/proposal/export-pptx`
- Azure configuration: `/health` reports endpoint and Key Vault status without
  exposing any secret values.
