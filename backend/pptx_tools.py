"""Local PPTX tool implementations shared by the API and the MCP server.

The functions in this module are deterministic.  An LLM may request a template
or propose a slide plan, but it never writes files or decides whether a plan is
valid by itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ppt_renderer import list_templates, render_pptx


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT_DIR / "templates"
STORAGE_DIR = ROOT_DIR / "storage"
PROPOSAL_DIR = STORAGE_DIR / "proposals"


def _manifest_paths() -> Iterable[Path]:
    return TEMPLATE_DIR.glob("*/manifest.json")


def _load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_template_manifests() -> Dict[str, List[Dict[str, str]]]:
    """Return templates that publish a machine-readable layout contract."""
    templates = []
    for path in _manifest_paths():
        manifest = _load_manifest(path)
        templates.append(
            {
                "template_id": str(manifest["template_id"]),
                "name": str(manifest.get("name") or manifest["template_id"]),
                "version": str(manifest.get("version") or "1.0.0"),
            }
        )
    return {"templates": sorted(templates, key=lambda item: item["template_id"])}


def get_template_manifest(template_id: str) -> Dict[str, Any]:
    """Load one local template contract without exposing arbitrary paths."""
    for path in _manifest_paths():
        manifest = _load_manifest(path)
        if manifest.get("template_id") == template_id:
            return manifest
    raise ValueError(f"Template manifest not found: {template_id}")


def list_layouts(template_id: str) -> Dict[str, Any]:
    manifest = get_template_manifest(template_id)
    return {
        "template_id": template_id,
        "layouts": manifest.get("layouts", []),
    }


def validate_slide_plan(template_id: str, slide_plan: Dict[str, Any] | List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate known layouts, required title/message, and density limits."""
    manifest = get_template_manifest(template_id)
    layouts = {
        layout.get("layout_id"): layout
        for layout in manifest.get("layouts", [])
        if isinstance(layout, dict) and layout.get("layout_id")
    }
    slides = slide_plan.get("slides", []) if isinstance(slide_plan, dict) else slide_plan
    errors = []

    if not isinstance(slides, list) or not slides:
        return {"valid": False, "errors": [{"code": "MISSING_SLIDES", "message": "At least one slide is required."}]}

    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            errors.append({"slide_id": f"S-{index:02d}", "code": "INVALID_SLIDE", "message": "Slide must be an object."})
            continue
        slide_id = str(slide.get("slide_id") or f"S-{index:02d}")
        layout_id = slide.get("layout_id")
        if layout_id not in layouts:
            errors.append({"slide_id": slide_id, "field": "layout_id", "code": "UNKNOWN_LAYOUT", "message": f"Unknown layout: {layout_id}."})
            continue
        if not str(slide.get("title") or "").strip():
            errors.append({"slide_id": slide_id, "field": "title", "code": "MISSING_TITLE", "message": "A slide title is required."})
        bullets = slide.get("bullets", [])
        if not isinstance(bullets, list):
            errors.append({"slide_id": slide_id, "field": "bullets", "code": "INVALID_BULLETS", "message": "Bullets must be an array."})
        elif len(bullets) > 5:
            errors.append({"slide_id": slide_id, "field": "bullets", "code": "TOO_MANY_BULLETS", "message": "Maximum 5 bullets are allowed."})
        elif any(len(" ".join(str(item).split())) > 118 for item in bullets):
            errors.append({"slide_id": slide_id, "field": "bullets", "code": "BULLET_TOO_LONG", "message": "Each bullet must be 118 characters or fewer."})

    return {"valid": not errors, "errors": errors}


def save_slide_plan(proposal_id: str, template_id: str, slides: List[Dict[str, Any]]) -> Path:
    """Persist only a validated plan under the local proposal workspace."""
    validation = validate_slide_plan(template_id, slides)
    if not validation["valid"]:
        raise ValueError(json.dumps(validation["errors"], ensure_ascii=False))
    proposal_path = PROPOSAL_DIR / proposal_id
    proposal_path.mkdir(parents=True, exist_ok=True)
    plan_path = proposal_path / "slide-plan.json"
    plan_path.write_text(json.dumps({"template_id": template_id, "slides": slides}, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path


def generate_pptx(proposal: Dict[str, Any], template_id: str) -> Dict[str, str]:
    """Render an approved proposal through the existing deterministic renderer."""
    output_path = render_pptx(proposal, template_id)
    return {"status": "completed", "output_path": str(output_path), "filename": output_path.name}


def configured_renderer_templates() -> Dict[str, Any]:
    """Expose legacy registry data for the UI while manifests are rolled out."""
    return list_templates()
