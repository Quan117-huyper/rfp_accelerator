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
GEMINI_MODEL="gemini-2.5-flash"
```

## Template Setup

- Put enterprise PPTX templates under `templates/<template_id>/template.pptx`
- Keep placeholder names consistent with the renderer
- Use `templates/template_registry.json` to register templates

## Checkpoints

- Backend health: `/health`
- Proposal analyze: `/proposal/analyze`
- Proposal upload: `/proposal/upload`
- PPT export: `/proposal/export-pptx`
