# Project Structure

This note describes where each kind of file belongs and which folders should be treated as source, runtime data, generated artifacts, or documentation.

## Root Layout

```text
usecase 3/
|-- backend/                  Python API, orchestration, agents, ingestion, PPTX export
|-- front-end/                React UI for upload, HITL, proposal review, export
|-- scripts/                  Repeatable local and E2E utility scripts
|-- templates/                PPTX templates and template registry
|-- storage/                  Runtime storage for uploads, previews, outputs, proposals
|-- generated/                Generated test fixtures, E2E outputs, exported PPTX files
|-- obsidian-vault/           Project knowledge base
|-- docs/                     Setup docs for integrations
|-- documentation/            Architecture and local MCP documentation
|-- apps/                     Local helper apps such as the PPTX MCP server
|-- modules/                  External or vendored modules such as PPTAgent/DeepPresenter
|-- database/                 Database-related assets if used by the app
|-- images/                   Static project screenshots and diagrams
|-- venv/                     Local Python virtual environment
|-- .env                      Local secrets and environment values, do not commit
|-- example.env               Safe example environment file
|-- requirements.txt          Python dependencies
|-- README.md                 Project entry README
```

## Source Code

Keep these folders under normal review and version control:

```text
backend/
front-end/src/
scripts/
templates/template_registry.json
apps/pptx_mcp_server/
obsidian-vault/
docs/
documentation/
```

Avoid mixing generated outputs into source folders. If a script creates a DOCX, PPTX, JSON checkpoint, preview image, or test artifact, write it under `generated/` or `storage/`.

## Backend

```text
backend/
|-- proposal_app.py           Flask API entrypoint and HTTP routes
|-- proposal_agent.py         Requirement, HITL, architect, proposal orchestration
|-- proposal_ingestion.py     DOCX/PDF/text parsing, metadata, token estimate, chunking
|-- foundry_published_agents.py
|                            Published Foundry agent adapter
|-- foundry_responses.py      Azure/OpenAI Responses-compatible calls
|-- azure_runtime.py          Azure runtime configuration and secret loading
|-- hitl_graph.py             Human-in-the-loop state transitions
|-- ppt_renderer.py           Local PPTX renderer using registered templates
|-- deep_presenter_renderer.py
|                            DeepPresenter/PPTAgent input bridge
|-- pptx_tools.py             PPTX helper utilities
|-- slide_planner.py          Slide planning helpers
|-- prompts.py                Prompt text and prompt helpers
|-- extraction.py             Extraction utilities
|-- chunking.py               Generic chunking utilities
|-- common/                   Azure storage/database helpers
|-- tests/                    Backend unit tests
```

Main API to run locally:

```powershell
.\venv\Scripts\python.exe backend\proposal_app.py --port 5000
```

## Frontend

```text
front-end/
|-- package.json              React scripts and dependency list
|-- public/                   Static browser assets
|-- src/
    |-- App.js                App routing/composition
    |-- pages/                Main workflow pages
    |-- components/layout/    Shared layout and sidebar
    |-- components/rfp/       RFP list, selector, artifact download components
```

Main local command:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3\front-end"
npm install
npm start
```

## Test And E2E Scripts

```text
scripts/
|-- create_e2e_rfp_fixture.py
|                            Creates realistic DOCX input for end-to-end tests
|-- create_ocr_pdf_fixtures.py
|                            Creates scanned-PDF and table-heavy PDF fixtures
|-- run_real_agent_e2e.py     Runs DOCX -> Requirement -> HITL -> Architect -> Proposal -> PPTX
|-- knowledge-indexing.py     Knowledge indexing utility
```

Preferred full workflow:

```powershell
cd "C:\Minhquan-22AD041\FPT\AI project\usecase 3"
.\venv\Scripts\python.exe scripts\create_e2e_rfp_fixture.py
.\venv\Scripts\python.exe scripts\create_ocr_pdf_fixtures.py
$env:E2E_TEMPLATE_ID = "master_template"
.\venv\Scripts\python.exe scripts\run_real_agent_e2e.py
```

Backend unit tests:

```powershell
.\venv\Scripts\python.exe -m unittest backend.tests.test_proposal_pipeline -v
```

## Templates

```text
templates/
|-- template_registry.json
|-- master_template/
    |-- template.pptx
|-- starter/
    |-- manifest.json
```

Rule of thumb:

- Put reusable enterprise PPTX files in `templates/<template_id>/template.pptx`.
- Register template metadata in `templates/template_registry.json`.
- Keep renderer-specific behavior in `backend/ppt_renderer.py`.
- Keep PPTAgent/DeepPresenter compatibility in `backend/deep_presenter_renderer.py`.

## Runtime And Generated Data

Runtime storage:

```text
storage/
|-- uploads/                  Uploaded customer files
|-- previews/                 Rendered document or slide previews
|-- outputs/                  API-generated output files
|-- proposals/                Proposal state and exported proposal artifacts
```

Generated test and E2E artifacts:

```text
generated/
|-- test-fixtures/            Realistic generated input files
|-- e2e-results/              Agent outputs, HITL answers, checkpoints, diagnostics
|-- proposal_*.pptx           Exported PowerPoint decks
```

Treat `generated/`, `storage/`, logs, and local virtual environments as disposable runtime artifacts unless a specific file is intentionally promoted to a fixture or documentation example.

## Obsidian Vault

```text
obsidian-vault/
|-- 00-Home.md                Navigation entry point
|-- 10-Scope.md               Product scope
|-- 15-Project-Structure.md   Folder and file ownership map
|-- 20-System-Map.md          End-to-end system flow
|-- 30-Backend-Modules.md     Backend module responsibilities
|-- 40-Frontend-Modules.md    Frontend module responsibilities
|-- 50-Provider-Options.md    Provider configuration notes
|-- 60-Runbook.md             Commands, tests, E2E workflow, troubleshooting
|-- 70-Backlog.md             Known follow-up work
```

Use this vault as the source of truth for project handoff notes. Put operational commands in `60-Runbook.md`; put architecture changes in `20-System-Map.md`; put module-level notes in `30-Backend-Modules.md` or `40-Frontend-Modules.md`.

## Cleanup Policy

Keep:

```text
backend/
front-end/src/
scripts/
templates/
obsidian-vault/
docs/
documentation/
apps/
requirements.txt
example.env
README.md
```

Review before committing:

```text
generated/e2e-results/*.json
generated/test-fixtures/*.docx
generated/*.pptx
storage/**
*.log
front-end/build/
```

Do not commit:

```text
.env
venv/
front-end/node_modules/
local secret files
temporary DeepPresenter/PPTAgent workspaces
```
