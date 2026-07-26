# Backend Modules
## Proposal Flow

- `backend/proposal_app.py`
  - `/health`
  - `/proposal/templates`
  - `/proposal/analyze`
  - `/proposal/upload`
  - `/proposal/generate`
  - `/proposal/export-pptx`
  - `/proposal/download/<filename>`

- `backend/proposal_agent.py`
  - requirement extraction
  - clarification question generation
  - AI pattern recommendation
  - proposal content generation
  - txt, pdf, and docx parsing

- `backend/ppt_renderer.py`
  - template registry lookup
  - placeholder replacement
  - starter deck generation when no enterprise template exists

## Notes

- Gemini is used when `GEMINI_API_KEY` exists.
- Local fallback keeps the workflow usable without external AI access.
- The backend now focuses only on proposal generation.
