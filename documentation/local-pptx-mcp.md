# Local PPTX MCP module

The demo keeps customer documents and PowerPoint artifacts on the local machine.
Azure Foundry supplies the Requirement and Architect agents; it does not receive
filesystem or renderer access.

```
React -> Flask proposal API -> published Foundry agents
                           -> local MCP server (stdio, optional)
                              -> template manifests + deterministic PPTX renderer
```

`apps/pptx_mcp_server/server.py` is a local stdio MCP server. It exposes
`list_templates`, `get_template`, `get_template_layouts`, `validate_plan`, and
`generate_deck`. It is not exposed to the Internet and is deliberately separate
from the published Foundry agents.

Run it only when testing MCP clients:

```powershell
python -m pip install -r apps/pptx_mcp_server/requirements.txt
python apps/pptx_mcp_server/server.py
```

The current Flask export endpoint continues to call the same deterministic
renderer directly. This keeps the user workflow working while making the tool
contract reusable for PPTAgent or a future Node `pptx-automizer` renderer.

Template manifests are stored under `templates/<template>/manifest.json`.
They define the supported layout IDs and density limits used to validate an LLM
slide plan before rendering. Add a manifest alongside every enterprise template
before allowing it into the proposal workflow.
