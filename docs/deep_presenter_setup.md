# DeepPresenter local setup

This project now supports two DeepPresenter profiles:

- `foundry_compat`: runs today with the Azure Foundry model already used by the app.
- `recommended`: follows the PPTAgent/DeepPresenter repository more closely and is meant for `Forceless/DeepPresenter-9B` plus optional Tavily, MinerU, and a text-to-image model.

## 1. Container

From [modules/PPTAgent](C:/Minhquan-22AD041/FPT/AI project/usecase 3/modules/PPTAgent):

```powershell
docker compose up -d
```

The host runtime should be available at [http://localhost:7861](http://localhost:7861).

## 2. Fast path: Foundry-compatible profile

This path keeps generation runnable with the existing Azure Foundry deployment.

Set:

```powershell
$env:DEEPPRESENTER_PROFILE = "foundry_compat"
```

The backend will use:

- [modules/PPTAgent/deeppresenter/config.foundry.yaml](C:/Minhquan-22AD041/FPT/AI project/usecase 3/modules/PPTAgent/deeppresenter/config.foundry.yaml)
- [modules/PPTAgent/deeppresenter/mcp.foundry.json](C:/Minhquan-22AD041/FPT/AI project/usecase 3/modules/PPTAgent/deeppresenter/mcp.foundry.json)

## 3. Recommended profile

This path is closer to the repository guidance.

Set:

```powershell
$env:DEEPPRESENTER_PROFILE = "recommended"
$env:DEEPPRESENTER_LOCAL_BASE_URL = "http://host.docker.internal:7811/v1"
$env:DEEPPRESENTER_LOCAL_MODEL = "Forceless/DeepPresenter-9B-GGUF"
$env:DEEPPRESENTER_LOCAL_API_KEY = "local"
```

Optional quality boosters:

```powershell
$env:TAVILY_API_KEY = "..."
$env:MINERU_API_KEY = "..."
# or
$env:MINERU_API_URL = "http://host.docker.internal:8000"
```

Optional image generation:

```powershell
$env:DEEPPRESENTER_T2I_BASE_URL = "http://host.docker.internal:9000/v1"
$env:DEEPPRESENTER_T2I_MODEL = "your-image-model"
$env:DEEPPRESENTER_T2I_API_KEY = "local"
```

The backend will use:

- [modules/PPTAgent/deeppresenter/config.recommended.yaml](C:/Minhquan-22AD041/FPT/AI project/usecase 3/modules/PPTAgent/deeppresenter/config.recommended.yaml)
- [modules/PPTAgent/deeppresenter/mcp.recommended.json](C:/Minhquan-22AD041/FPT/AI project/usecase 3/modules/PPTAgent/deeppresenter/mcp.recommended.json)

## 4. What the app does now

When `presentation_pipeline = "deep_presenter"`:

1. the backend writes a proposal brief and full proposal context into `modules/PPTAgent/workspace/...`
2. the backend launches DeepPresenter `AgentLoop`
3. DeepPresenter runs `Research -> PPTAgent`
4. the final PPTX is copied into [generated](C:/Minhquan-22AD041/FPT/AI project/usecase 3/generated)

## 5. Important note

`recommended` only becomes truly "the same as the repo showcase" after you supply:

- a working local or remote endpoint for `Forceless/DeepPresenter-9B`
- Tavily if you want stronger web research
- MinerU if you want stronger PDF parsing
- an image model if you want richer auto-created visuals
