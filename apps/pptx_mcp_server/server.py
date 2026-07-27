"""Local stdio MCP server for proposal template and rendering tools.

Run from the repository root with:
    python apps/pptx_mcp_server/server.py

It is intentionally local-only. Flask can later use this server as a stdio
client without exposing templates or customer documents to the Internet.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pptx_tools import (  # noqa: E402
    generate_pptx,
    get_template_manifest,
    list_layouts,
    list_template_manifests,
    validate_slide_plan,
)


try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised when running the optional server
    raise SystemExit("Install optional MCP dependencies first: pip install -r apps/pptx_mcp_server/requirements.txt") from exc


mcp = FastMCP("proposal-pptx-tools")


@mcp.tool()
def list_templates() -> Dict[str, Any]:
    """List local proposal templates that provide a manifest."""
    return list_template_manifests()


@mcp.tool()
def get_template(template_id: str) -> Dict[str, Any]:
    """Return the layout and content limits for a local template."""
    return get_template_manifest(template_id)


@mcp.tool()
def get_template_layouts(template_id: str) -> Dict[str, Any]:
    """Return only layouts supported by a local template."""
    return list_layouts(template_id)


@mcp.tool()
def validate_plan(template_id: str, slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate a proposed slide plan before rendering."""
    return validate_slide_plan(template_id, slides)


@mcp.tool()
def generate_deck(proposal: Dict[str, Any], template_id: str) -> Dict[str, str]:
    """Render an approved proposal to a local PPTX output file."""
    if proposal.get("architecture_approved") is not True:
        raise ValueError("Architecture approval is required before PPTX generation.")
    return generate_pptx(proposal, template_id)


if __name__ == "__main__":
    mcp.run()
