# System Map
## High-Level Flow

```mermaid
flowchart LR
  A[User pastes or uploads a requirement document] --> B[React proposal page]
  B --> C[Flask proposal API]
  C --> D[Requirement extraction]
  D --> E[Clarification questions]
  D --> F[Proposal generation]
  F --> G[PPT template renderer]
  G --> H[Generated PPTX file]
```

## Main Building Blocks

- React frontend
- Flask proposal API
- proposal agent logic
- template-driven PPT renderer
- local generated-file storage

## Provider Layers

- Gemini API when `GEMINI_API_KEY` is set
- deterministic local fallback when no API key is available

## Storage Layers

- local source upload handling
- local `generated/` output for PPTX files
- template files under `templates/`
