"""DeepPresenter-backed PPTX rendering adapter.

This adapter keeps the proposal workflow intact and adds a second
presentation pipeline that renders proposal content through the local
DeepPresenter runtime. Unlike the starter renderer, this path runs the
repository's AgentLoop orchestration so research, tool use, and PPTAgent
template generation follow the upstream flow more closely.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from azure_runtime import load_azure_runtime_configuration


ROOT_DIR = Path(__file__).resolve().parent.parent
PPTAGENT_DIR = ROOT_DIR / "modules" / "PPTAgent"
PPTAGENT_WORKSPACE = PPTAGENT_DIR / "workspace"
RUNNER_PATH = "/opt/workspace/run_deep_presenter_stack.py"
DEFAULT_CONTAINER = os.getenv("DEEPPRESENTER_CONTAINER_NAME", "deeppresenter-host")
SUPPORTED_PPTAGENT_TEMPLATES = {"default", "thu", "cip", "ucas", "beamer", "hit"}

load_dotenv(ROOT_DIR / ".env")
load_azure_runtime_configuration()


def _resolve_deeppresenter_template(template_id: str) -> str:
    candidate = str(template_id or "").strip()
    if candidate in SUPPORTED_PPTAGENT_TEMPLATES:
        return candidate
    return os.getenv("DEEPPRESENTER_DEFAULT_TEMPLATE", "default").strip() or "default"


def _proposal_output_dir() -> Path:
    output_dir = ROOT_DIR / "generated"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def _compact(text: Any, limit: int = 120) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rsplit(" ", 1)[0] + "..."


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _slide_type_to_layout(slide_type: str) -> str:
    mapping = {
        "title": "layout_title",
        "customer_context": "layout_kv",
        "problem_impact": "layout_bullets",
        "goals_kpi": "layout_kv",
        "capability_summary": "layout_bullets",
        "solution_overview": "layout_bullets",
        "process_flow": "layout_process",
        "business_flow": "layout_process",
        "logical_architecture": "layout_diagram",
        "high_level_architecture": "layout_diagram",
        "component_cards": "layout_components",
        "infrastructure_security": "layout_kv",
        "cost_table": "layout_table",
        "cost": "layout_table",
        "roadmap": "layout_process",
        "benefits_roadmap": "layout_process",
        "next_steps": "layout_bullets",
    }
    return mapping.get(slide_type, "layout_bullets")


def _normalize_open_items(proposal: Dict[str, Any]) -> List[str]:
    open_items = proposal.get("open_items", [])
    normalized = []
    for item in open_items:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict):
            title = str(item.get("title") or "").strip()
            description = str(item.get("description") or "").strip()
            if title and description:
                normalized.append(f"{title}: {description}")
            elif title:
                normalized.append(title)
            elif description:
                normalized.append(description)
    return normalized


def proposal_to_pptagent_input(proposal: Dict[str, Any], template_id: str) -> Dict[str, Any]:
    """Convert proposal output into the slide-plan contract expected by PPTAgent."""
    published_input = proposal.get("pptagent_input") if isinstance(proposal.get("pptagent_input"), dict) else {}
    published_slides = published_input.get("slides") if isinstance(published_input, dict) else []
    if isinstance(published_slides, list) and published_slides:
        return {
            "pptagent_input": {
                "template_id": template_id,
                "deck_title": _compact(
                    published_input.get("deck_title")
                    or proposal.get("proposal_title")
                    or proposal.get("deck_title")
                    or "Customer Proposal",
                    80,
                ),
                "subtitle": _compact(published_input.get("subtitle") or proposal.get("executive_summary") or "", 140),
                "recommended_slide_count": int(published_input.get("recommended_slide_count") or len(published_slides)),
                "deck_rationale": _compact(
                    published_input.get("deck_rationale")
                    or proposal.get("executive_summary")
                    or "Structured proposal deck generated from approved requirements and architecture.",
                    240,
                ),
                "slides": published_slides,
                "open_items": published_input.get("open_items") or _normalize_open_items(proposal),
                "rendering_notes": {
                    **(published_input.get("rendering_notes") if isinstance(published_input.get("rendering_notes"), dict) else {}),
                    "preserve_template_branding": True,
                    "do_not_shrink_text_to_fit": True,
                    "use_supported_layouts_only": True,
                    "source": "published_proposal_agent_pptagent_input",
                },
            }
        }

    raw_slides = proposal.get("slide_plan") or []
    slides = []
    for index, slide in enumerate(raw_slides, start=1):
        if not isinstance(slide, dict):
            continue
        slide_type = str(slide.get("slide_type") or "content")
        title = str(slide.get("title") or f"Slide {index}").strip()
        bullets = [_compact(item) for item in _as_list(slide.get("bullets"))][:5]
        component_cards = []
        for card in slide.get("component_cards", [])[:3]:
            if not isinstance(card, dict):
                continue
            component_cards.append(
                {
                    "component_id": str(card.get("component_id") or card.get("id") or f"COMP-{index:03d}"),
                    "line_1_name": _compact(card.get("display_name") or card.get("line_1_name") or "Component", 60),
                    "line_2_purpose": _compact(card.get("short_purpose") or card.get("line_2_purpose") or "", 92),
                    "line_3_requirement_ids": [
                        str(item)
                        for item in card.get("requirement_ids", card.get("line_3_requirement_ids", []))
                    ],
                }
            )
        slides.append(
            {
                "slide_id": str(slide.get("slide_id") or f"S-{index:02d}"),
                "slide_type": slide_type,
                "layout_id": _slide_type_to_layout(slide_type),
                "narrative_role": str(slide.get("narrative_role") or slide_type),
                "primary_message": _compact(
                    slide.get("key_message")
                    or slide.get("primary_message")
                    or (bullets[0] if bullets else title),
                    170,
                ),
                "title": title,
                "subtitle": "",
                "content": {
                    "bullets": bullets,
                    "key_value_pairs": [],
                    "component_cards": component_cards,
                    "process_steps": [],
                    "diagram": {"nodes": [], "connections": []},
                    "table": {"columns": [], "rows": []},
                },
                "requirement_ids": [str(item) for item in slide.get("requirement_ids", [])],
                "component_ids": [
                    str(item.get("component_id") or item.get("id"))
                    for item in slide.get("component_cards", [])
                    if isinstance(item, dict) and (item.get("component_id") or item.get("id"))
                ],
                "evidence_ids": [str(item) for item in slide.get("evidence_ids", [])],
                "assumption_ids": [str(item) for item in slide.get("assumption_ids", [])],
                "speaker_notes": _compact(slide.get("key_message") or title, 220),
            }
        )

    if not slides:
        slides.append(
            {
                "slide_id": "S-01",
                "slide_type": "title",
                "layout_id": "layout_title",
                "narrative_role": "opening",
                "primary_message": _compact(proposal.get("executive_summary") or "Proposal overview"),
                "title": _compact(proposal.get("proposal_title") or "AI Solution Proposal", 70),
                "subtitle": _compact(proposal.get("executive_summary") or "", 120),
                "content": {
                    "bullets": [_compact(item) for item in _as_list(proposal.get("business_solution"))][:3],
                    "key_value_pairs": [],
                    "component_cards": [],
                    "process_steps": [],
                    "diagram": {"nodes": [], "connections": []},
                    "table": {"columns": [], "rows": []},
                },
                "requirement_ids": [],
                "component_ids": [],
                "evidence_ids": [],
                "assumption_ids": [],
                "speaker_notes": _compact(proposal.get("executive_summary") or "", 220),
            }
        )

    return {
        "pptagent_input": {
            "template_id": template_id,
            "deck_title": _compact(
                proposal.get("proposal_title")
                or proposal.get("deck_title")
                or "Customer Proposal",
                80,
            ),
            "subtitle": _compact(proposal.get("executive_summary") or "", 140),
            "recommended_slide_count": len(slides),
            "deck_rationale": _compact(
                proposal.get("executive_summary")
                or "Structured proposal deck generated from approved requirements and architecture.",
                240,
            ),
            "slides": slides,
            "open_items": _normalize_open_items(proposal),
            "rendering_notes": {
                "preserve_template_branding": True,
                "do_not_shrink_text_to_fit": True,
                "use_supported_layouts_only": True,
            },
        }
    }


def _proposal_brief_markdown(proposal: Dict[str, Any], template_id: str) -> str:
    ppt_input = proposal_to_pptagent_input(proposal, template_id)["pptagent_input"]
    lines = [
        f"# {ppt_input['deck_title']}",
        "",
        ppt_input["subtitle"] or "Customer-ready proposal deck.",
        "",
        "## Proposal constraints",
        "- Use enterprise tone and keep the deck customer-facing.",
        "- Preserve branding and avoid shrinking text to fit.",
        "- Prefer structured diagrams, tables, and concise bullets.",
        "",
        "## Planned slides",
    ]
    for slide in ppt_input["slides"]:
        lines.append(f"### {slide['slide_id']} — {slide['title']}")
        lines.append(f"- Primary message: {slide['primary_message']}")
        if slide["content"]["bullets"]:
            lines.append("- Bullets:")
            for bullet in slide["content"]["bullets"]:
                lines.append(f"  - {bullet}")
        if slide["content"]["component_cards"]:
            lines.append("- Components:")
            for card in slide["content"]["component_cards"]:
                req_ids = ", ".join(card["line_3_requirement_ids"]) or "None"
                lines.append(f"  - {card['line_1_name']}: {card['line_2_purpose']} ({req_ids})")
        if slide["requirement_ids"]:
            lines.append(f"- Requirement IDs: {', '.join(slide['requirement_ids'])}")
        lines.append("")
    if ppt_input["open_items"]:
        lines.extend(["## Open items", *[f"- {item}" for item in ppt_input["open_items"]], ""])
    return "\n".join(lines).strip() + "\n"


def proposal_to_deeppresenter_prompt(proposal: Dict[str, Any], template_id: str) -> str:
    ppt_input = proposal_to_pptagent_input(proposal, template_id)["pptagent_input"]
    return "\n".join(
        [
            f"Create a customer-ready PowerPoint deck titled '{ppt_input['deck_title']}'.",
            "Use the attached proposal brief as the source of truth for storyline, component mapping, and requirement traceability.",
            "Generate a polished enterprise presentation for a proposal review audience.",
            "Use diagrams, structured component groupings, concise tables, and presentation-friendly bullets where helpful.",
            "Do not invent new Azure services, customer commitments, KPIs, or costs beyond the attached proposal context.",
            "If the brief contains open items, keep them as TBD rather than fabricating an answer.",
            f"Target approximately {ppt_input['recommended_slide_count']} slides.",
            f"Preferred template identifier: {template_id}.",
        ]
    )


def _profile_paths(profile_name: str) -> tuple[Path, Path]:
    profile_map = {
        "foundry_compat": ("config.foundry.yaml", "mcp.foundry.json"),
        "recommended": ("config.recommended.yaml", "mcp.recommended.json"),
    }
    config_name, mcp_name = profile_map.get(profile_name, profile_map["recommended"])
    return PPTAGENT_DIR / "deeppresenter" / config_name, PPTAGENT_DIR / "deeppresenter" / mcp_name


def _docker_exec(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def render_with_deep_presenter(proposal: Dict[str, Any], template_id: str) -> Path:
    if not PPTAGENT_WORKSPACE.exists():
        raise ValueError("modules/PPTAgent/workspace was not found. Clone/setup PPTAgent first.")

    run_id = uuid.uuid4().hex[:10]
    pptagent_template_id = _resolve_deeppresenter_template(template_id)
    host_run_dir = PPTAGENT_WORKSPACE / f"proposal-agent-run-{run_id}"
    host_run_dir.mkdir(parents=True, exist_ok=True)
    host_output = host_run_dir / "proposal_deeppresenter_output.pptx"
    host_prompt = host_run_dir / "proposal_prompt.txt"
    host_brief = host_run_dir / "proposal_brief.md"
    host_context = host_run_dir / "proposal_context.json"
    host_prompt.write_text(proposal_to_deeppresenter_prompt(proposal, pptagent_template_id), encoding="utf-8")
    host_brief.write_text(_proposal_brief_markdown(proposal, pptagent_template_id), encoding="utf-8")
    host_context.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")

    inspect_result = _docker_exec(["docker", "inspect", DEFAULT_CONTAINER])
    if inspect_result.returncode != 0:
        raise ValueError(
            "DeepPresenter container is not running. Start it with docker compose up -d in modules/PPTAgent."
        )

    container_workspace = f"/opt/workspace/{host_run_dir.name}"
    container_output = f"{container_workspace}/proposal_deeppresenter_output.pptx"
    container_prompt = f"{container_workspace}/proposal_prompt.txt"
    container_brief = f"{container_workspace}/proposal_brief.md"
    container_context = f"{container_workspace}/proposal_context.json"
    profile_name = os.getenv("DEEPPRESENTER_PROFILE", "recommended").strip() or "recommended"
    config_path, mcp_path = _profile_paths(profile_name)

    envs = [
        "FOUNDRY_API_KEY",
        "TAVILY_API_KEY",
        "SERPAPI_KEY",
        "MINERU_API_KEY",
        "MINERU_API_URL",
        "DEEPPRESENTER_LOCAL_BASE_URL",
        "DEEPPRESENTER_LOCAL_MODEL",
        "DEEPPRESENTER_LOCAL_API_KEY",
        "DEEPPRESENTER_VISION_BASE_URL",
        "DEEPPRESENTER_VISION_MODEL",
        "DEEPPRESENTER_VISION_API_KEY",
        "DEEPPRESENTER_T2I_BASE_URL",
        "DEEPPRESENTER_T2I_MODEL",
        "DEEPPRESENTER_T2I_API_KEY",
    ]

    command = [
        "docker",
        "exec",
        "-e",
        f"DEEPPRESENTER_CONFIG_FILE=/usr/src/pptagent/deeppresenter/{config_path.name}",
        "-e",
        f"DEEPPRESENTER_MCP_FILE=/usr/src/pptagent/deeppresenter/{mcp_path.name}",
        "-e",
        f"PPT_PROMPT_FILE={container_prompt}",
        "-e",
        f"PPT_ATTACHMENTS_JSON={json.dumps([container_brief, container_context])}",
        "-e",
        f"PPT_TEMPLATE={pptagent_template_id}",
        "-e",
        f"PPT_NUM_PAGES={len(proposal_to_pptagent_input(proposal, pptagent_template_id)['pptagent_input']['slides'])}",
        "-e",
        f"PPT_WORKSPACE={container_workspace}",
        "-e",
        f"PPT_OUTPUT={container_output}",
        "-e",
        f"CONFIG_FILE=/usr/src/pptagent/deeppresenter/{config_path.name}",
        DEFAULT_CONTAINER,
        "/opt/.venv/bin/python",
        RUNNER_PATH,
    ]
    for env_name in envs:
        env_value = os.getenv(env_name)
        if env_value:
            command[2:2] = ["-e", f"{env_name}={env_value}"]
    result = _docker_exec(command)
    if result.returncode != 0:
        raise RuntimeError(
            "DeepPresenter render failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    if not host_output.exists():
        raise RuntimeError(
            "DeepPresenter reported success but no PPTX was created. "
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    final_path = _proposal_output_dir() / f"proposal_deep_presenter_{proposal['proposal_id']}.pptx"
    shutil.copy2(host_output, final_path)
    return final_path
