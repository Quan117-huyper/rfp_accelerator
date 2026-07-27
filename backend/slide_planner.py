"""Deterministic proposal storyline and slide-plan builder.

The LLM writes approved proposal content. This module turns that content into a
stable, customer-facing narrative so the renderer never has to infer a slide
layout from a long JSON paragraph.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


SLIDE_BLUEPRINT = [
    ("customer_context", "why_change", "Customer Context", "context"),
    ("problem_statement", "why_change", "Key Problems and Impacts", "problem-impact"),
    ("goals", "what_success_looks_like", "Goals and Success Criteria", "goal-metrics"),
    ("solution_overview", "what_we_propose", "Proposed Solution at a Glance", "problem-capability-value"),
    ("business_flow", "how_the_workflow_operates", "End-to-End Solution Flow", "process-flow"),
    ("high_level_architecture", "how_it_works", "High-Level Logical Architecture", "layered-architecture"),
    ("design_differentiators", "why_this_design", "Key Design Differentiators", "differentiator-cards"),
    ("infrastructure_security", "how_it_runs_safely", "Infrastructure, Security and Operations", "infra-security"),
    ("cost", "what_it_costs", "Environment Cost View", "cost-table"),
    ("benefits_roadmap", "what_happens_next", "Benefits and Delivery Roadmap", "roadmap"),
]

LAYER_COLORS = {
    "user_integration": "teal",
    "document_processing": "amber",
    "ai_intelligence": "purple",
    "data_knowledge": "blue",
    "proposal_pptx": "rose",
    "security_operations": "slate",
}


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if value else []


def _compact(value: Any, limit: int = 118) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0] + "..."


def _component_layer(component: Dict[str, Any]) -> str:
    text = f"{component.get('service', '')} {component.get('purpose', '')}".lower()
    if any(term in text for term in ("entra", "graph", "integration", "sharepoint", "salesforce", "api gateway")):
        return "user_integration"
    if any(term in text for term in ("document", "parser", "ocr", "chunk")):
        return "document_processing"
    if any(term in text for term in ("foundry", "openai", "agent", "reasoning", "model")):
        return "ai_intelligence"
    if any(term in text for term in ("search", "storage", "database", "queue", "blob", "knowledge")):
        return "data_knowledge"
    if any(term in text for term in ("template", "pptx", "powerpoint", "renderer", "proposal")):
        return "proposal_pptx"
    return "security_operations"


def normalize_components(components: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create presentation cards with one service only once per view."""
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for index, component in enumerate(components or [], start=1):
        if not isinstance(component, dict):
            continue
        name = str(component.get("service") or component.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        layer = str(component.get("layer") or _component_layer(component))
        normalized.append(
            {
                "component_id": str(component.get("id") or f"COMP-{index:03d}"),
                "display_name": _compact(component.get("display_name") or name, 54),
                "technology": _as_list(component.get("technology")) or [name],
                "layer": layer,
                "color_group": LAYER_COLORS.get(layer, "slate"),
                "short_purpose": _compact(component.get("short_purpose") or component.get("purpose"), 92),
                "requirement_ids": _as_list(component.get("requirement_ids")),
                "classification": component.get("classification", "optional_for_poc"),
                "diagram_priority": component.get("diagram_priority", "medium"),
            }
        )
    return normalized


def _slide(slide_type: str, narrative_role: str, title: str, layout_id: str, message: str, bullets: List[str], **extra: Any) -> Dict[str, Any]:
    return {
        "slide_id": f"S-{len(extra.get('previous_slides', [])) + 1:02d}",
        "slide_type": slide_type,
        "narrative_role": narrative_role,
        "layout_id": layout_id,
        "title": title,
        "key_message": _compact(message, 138),
        "bullets": [_compact(item, 118) for item in bullets if item][:5],
        "source_ids": extra.get("source_ids", []),
        "requirement_ids": extra.get("requirement_ids", []),
        "component_cards": extra.get("component_cards", []),
    }


def build_slide_plan(proposal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a ten-slide proposal storyline from approved proposal content."""
    architecture = proposal.get("architecture_decisions") or {}
    components = normalize_components(architecture.get("components", [])) if isinstance(architecture, dict) else []
    requirements = proposal.get("extracted_requirements") or {}
    business_goals = _as_list(requirements.get("business_goals"))
    functional = _as_list(requirements.get("functional_requirements"))
    nfrs = _as_list(requirements.get("non_functional_requirements"))
    security = _as_list(requirements.get("security_needs"))
    constraints = _as_list(requirements.get("constraints"))
    patterns = _as_list(architecture.get("selected_patterns")) if isinstance(architecture, dict) else []

    process = [
        "Upload requirement document",
        "Parse natively; use OCR only when needed",
        "Extract and validate requirements",
        "Human clarification and approval",
        "Research and architecture decision",
        "Generate proposal content and render PPTX",
    ]
    planner: List[Dict[str, Any]] = []
    previous = []
    entries = [
        _slide("customer_context", "why_change", "Customer Context", "context", proposal.get("problem_statement") or proposal.get("executive_summary"), business_goals or functional[:3], previous_slides=previous, requirement_ids=["business_goals", "functional_requirements"]),
        _slide("problem_statement", "why_change", "Key Problems and Impacts", "problem-impact", proposal.get("problem_statement") or "The current process requires a controlled, repeatable proposal workflow.", _as_list(proposal.get("problem_statement")), previous_slides=previous, source_ids=["problem_statement"]),
        _slide("goals", "what_success_looks_like", "Goals and Success Criteria", "goal-metrics", "The proposal workflow is measured by business outcomes and acceptance criteria.", business_goals or nfrs or constraints, previous_slides=previous, requirement_ids=["business_goals", "non_functional_requirements"]),
        _slide("solution_overview", "what_we_propose", "Proposed Solution at a Glance", "problem-capability-value", "A human-governed AI workflow turns requirements into a traceable architecture and branded proposal.", _as_list(proposal.get("business_solution")), previous_slides=previous, component_cards=components[:4]),
        _slide("business_flow", "how_the_workflow_operates", "End-to-End Solution Flow", "process-flow", "Human approval occurs before architecture and final proposal generation.", process, previous_slides=previous, requirement_ids=["functional_requirements"]),
        _slide("high_level_architecture", "how_it_works", "High-Level Logical Architecture", "layered-architecture", "Modular services implement the approved capabilities without coupling AI content to presentation layout.", [card["display_name"] + ": " + card["short_purpose"] for card in components], previous_slides=previous, component_cards=components),
        _slide("design_differentiators", "why_this_design", "Key Design Differentiators", "differentiator-cards", "The design uses controlled AI and deterministic workflow steps where they matter.", patterns + ["Conditional OCR", "Evidence-backed architecture", "Deterministic template rendering"], previous_slides=previous),
        _slide("infrastructure_security", "how_it_runs_safely", "Infrastructure, Security and Operations", "infra-security", "Security and operations support the workflow without obscuring its business value.", security + nfrs + [card["display_name"] for card in components if card["layer"] == "security_operations"], previous_slides=previous, requirement_ids=["security_needs", "non_functional_requirements"]),
        _slide("cost", "what_it_costs", "Environment Cost View", "cost-table", "Costs are shown by environment and only use approved assumptions.", [f"{item.get('environment', 'Environment')}: {item.get('monthly_estimate_usd', 'TBD')}" for item in proposal.get("cost_estimation", []) if isinstance(item, dict)] or constraints or ["Development, Test, and UAT/Staging estimates require approved usage assumptions."], previous_slides=previous, requirement_ids=["constraints"]),
        _slide("benefits_roadmap", "what_happens_next", "Benefits and Delivery Roadmap", "roadmap", "The implementation delivers a reviewable workflow first, then hardens it for production.", _as_list(proposal.get("implementation_approach")) + _as_list(proposal.get("delivery_notes")), previous_slides=previous),
    ]
    for entry in entries:
        entry["slide_id"] = f"S-{len(planner) + 1:02d}"
        planner.append(entry)
    return validate_slide_plan(planner)


def validate_slide_plan(slides: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enforce one message and compact, renderer-safe content per slide."""
    valid: List[Dict[str, Any]] = []
    for slide in slides:
        if not isinstance(slide, dict) or not slide.get("slide_type") or not slide.get("key_message"):
            continue
        slide = dict(slide)
        slide["title"] = _compact(slide.get("title"), 64)
        slide["key_message"] = _compact(slide.get("key_message"), 138)
        slide["bullets"] = [_compact(item, 118) for item in _as_list(slide.get("bullets"))][:5]
        seen = set()
        cards = []
        for card in slide.get("component_cards", []):
            if not isinstance(card, dict):
                continue
            key = str(card.get("display_name", "")).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            cards.append(card)
        slide["component_cards"] = cards
        valid.append(slide)
    return valid
