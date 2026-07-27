"""Persistent Human-in-the-Loop orchestration for the proposal workflow.

The graph owns workflow state. The browser only renders interrupt payloads and
submits one consolidated response for each review checkpoint.
"""

from __future__ import annotations

import atexit
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from proposal_agent import analyze_document, generate_proposal, research_architecture
from proposal_ingestion import ingest_text, ingest_upload


ROOT_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT_DIR / "database"
STATE_DIR.mkdir(exist_ok=True)
STATE_DB = STATE_DIR / "hitl_state.db"


class HITLState(TypedDict, total=False):
    document_text: str
    filename: str
    ingestion: Dict[str, Any]
    template_id: str
    research_mode: str
    project_context: Dict[str, Any]
    extraction: Dict[str, Any]
    agent_requirements: Dict[str, Any]
    clarification_questions: List[Dict[str, Any]]
    clarifications: Dict[str, str]
    clarification_decision: str
    architecture_review_feedback: str
    research_result: Dict[str, Any]
    architecture_decision: str
    cost_assumptions: List[Dict[str, Any]]
    proposal: Dict[str, Any]
    status: str
    error: Optional[str]
    thread_id: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _emit(**values: Any) -> Dict[str, Any]:
    values["updated_at"] = _now()
    return values


def _thread_id() -> str:
    return f"proposal-{uuid.uuid4().hex[:12]}"


def _config(thread_id: str) -> Dict[str, Dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _flatten_costs(architecture: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for environment, values in (architecture.get("cost_estimate") or {}).items():
        for value in values or []:
            if isinstance(value, dict):
                rows.append({"environment": environment, **value})
    return rows


def extract_node(state: HITLState) -> Dict[str, Any]:
    text = (state.get("document_text") or "").strip()
    if not text:
        return _emit(status="failed", error="document_text is required")

    ingestion = state.get("ingestion") or ingest_text(text, state.get("filename") or "requirements.txt")
    analysis = analyze_document(ingestion)
    if analysis.get("extraction_mode") in {"failed", "unavailable"}:
        return _emit(
            status="failed",
            extraction=analysis,
            error=(analysis.get("provider_errors") or ["Published Requirement Agent failed."])[0],
        )

    return _emit(
        status="awaiting_requirement_review",
        extraction=analysis,
        agent_requirements=analysis.get("agent_requirements") or {},
        clarification_questions=analysis.get("clarification_questions") or [],
    )


def route_after_extract(state: HITLState) -> str:
    return END if state.get("status") == "failed" else "requirement_review"


def requirement_review_node(state: HITLState) -> Dict[str, Any]:
    payload = {
        "type": "requirement_review",
        "title": "Clarify the requirement before architecture",
        "questions": state.get("clarification_questions") or [],
        "requirements": state.get("agent_requirements") or {},
        "traceability": (state.get("extraction") or {}).get("traceability") or {},
        "resume_payload_shape": {
            "decision": "approved | skipped",
            "clarifications": {"question_field": "answer"},
            "additional_instruction": "optional instruction for the architect",
            "research_mode": "off | azure_official_only | azure_github_papers",
        },
    }
    response = interrupt(payload)
    if not isinstance(response, dict):
        return _emit(status="failed", error="Requirement review response must be an object.")

    answers = response.get("clarifications")
    clarifications = {str(key): str(value).strip() for key, value in (answers or {}).items() if str(value).strip()} if isinstance(answers, dict) else {}
    instruction = str(response.get("additional_instruction") or "").strip()
    if instruction:
        clarifications["hitl_review"] = instruction
    requested_research_mode = str(response.get("research_mode") or state.get("research_mode") or "azure_official_only")
    if requested_research_mode not in {"off", "azure_official_only", "azure_github_papers"}:
        requested_research_mode = state.get("research_mode") or "azure_official_only"

    return _emit(
        status="researching",
        clarification_decision=str(response.get("decision") or "approved").lower(),
        clarifications=clarifications,
        research_mode=requested_research_mode,
    )


def research_node(state: HITLState) -> Dict[str, Any]:
    extraction = state.get("extraction") or {}
    project_context = dict(state.get("project_context") or {})
    feedback = str(state.get("architecture_review_feedback") or "").strip()
    if feedback:
        project_context["architecture_review_feedback"] = feedback

    result = research_architecture(
        extraction.get("extracted") or {},
        clarifications=state.get("clarifications") or {},
        research_mode=state.get("research_mode") or "azure_official_only",
        project_context=project_context,
        agent_requirements=state.get("agent_requirements") or {},
    )
    if result.get("mode") in {"failed", "unavailable"}:
        return _emit(status="failed", research_result=result, error=result.get("error") or "Published Architect Agent failed.")

    architecture = result.get("architecture") or {}
    return _emit(
        status="awaiting_architecture_approval",
        research_result=result,
        cost_assumptions=_flatten_costs(architecture),
        architecture_decision="pending",
    )


def architecture_review_node(state: HITLState) -> Dict[str, Any]:
    result = state.get("research_result") or {}
    architecture = result.get("architecture") or {}
    payload = {
        "type": "architecture_review",
        "title": "Review the architecture decision",
        "architecture": architecture,
        "sources": result.get("sources") or [],
        "cost_assumptions": state.get("cost_assumptions") or [],
        "resume_payload_shape": {
            "decision": "approved | changes_requested",
            "feedback": "required when changes_requested",
            "cost_assumptions": "optional list of edited rows",
        },
    }
    response = interrupt(payload)
    if not isinstance(response, dict):
        return _emit(status="failed", error="Architecture review response must be an object.")

    decision = str(response.get("decision") or "approved").lower()
    costs = response.get("cost_assumptions")
    return _emit(
        status="generating" if decision == "approved" else "researching",
        architecture_decision=decision,
        architecture_review_feedback=str(response.get("feedback") or "").strip(),
        cost_assumptions=[item for item in costs if isinstance(item, dict)] if isinstance(costs, list) else state.get("cost_assumptions") or [],
    )


def route_after_architecture_review(state: HITLState) -> str:
    if state.get("architecture_decision") == "approved":
        return "generate"
    if state.get("architecture_decision") == "changes_requested":
        return "research"
    return END


def generate_node(state: HITLState) -> Dict[str, Any]:
    extraction = state.get("extraction") or {}
    architecture = (state.get("research_result") or {}).get("architecture") or {}
    proposal = generate_proposal(
        extracted=extraction.get("extracted") or {},
        clarifications=state.get("clarifications") or {},
        architecture_decisions=architecture,
        cost_assumptions=state.get("cost_assumptions") or [],
        template_id=state.get("template_id") or "starter",
        architecture_approved=True,
        confirmed_requirements=state.get("agent_requirements") or {},
    )
    if proposal.get("generation_mode") == "failed":
        return _emit(status="failed", proposal=proposal, error=proposal.get("generation_error") or "Published Proposal Agent failed.")
    proposal["hitl"] = {
        "thread_id": state.get("thread_id"),
        "requirement_review": state.get("clarification_decision"),
        "architecture_approved_at": _now(),
    }
    return _emit(status="completed", proposal=proposal)


_connection = sqlite3.connect(str(STATE_DB), check_same_thread=False)
atexit.register(_connection.close)
HITL_GRAPH = StateGraph(HITLState)
HITL_GRAPH.add_node("extract", extract_node)
HITL_GRAPH.add_node("requirement_review", requirement_review_node)
HITL_GRAPH.add_node("research", research_node)
HITL_GRAPH.add_node("architecture_review", architecture_review_node)
HITL_GRAPH.add_node("generate", generate_node)
HITL_GRAPH.add_edge(START, "extract")
HITL_GRAPH.add_conditional_edges("extract", route_after_extract, {"requirement_review": "requirement_review", END: END})
HITL_GRAPH.add_edge("requirement_review", "research")
HITL_GRAPH.add_edge("research", "architecture_review")
HITL_GRAPH.add_conditional_edges(
    "architecture_review",
    route_after_architecture_review,
    {"research": "research", "generate": "generate", END: END},
)
HITL_GRAPH.add_edge("generate", END)
HITL_GRAPH = HITL_GRAPH.compile(checkpointer=SqliteSaver(_connection))


PUBLIC_FIELDS = (
    "status", "error", "thread_id", "updated_at", "template_id", "filename", "extraction",
    "agent_requirements", "clarification_questions", "clarifications", "clarification_decision",
    "research_mode", "research_result", "architecture_decision", "cost_assumptions", "proposal",
)


def _snapshot_payload(thread_id: str) -> Dict[str, Any]:
    snapshot = HITL_GRAPH.get_state(_config(thread_id))
    values = dict(snapshot.values or {})
    interrupt_payload = None
    for task in snapshot.tasks or ():
        for item in getattr(task, "interrupts", ()) or ():
            interrupt_payload = getattr(item, "value", None)
            if interrupt_payload:
                break
        if interrupt_payload:
            break
    return {
        "thread_id": thread_id,
        "state": {key: values[key] for key in PUBLIC_FIELDS if key in values},
        "interrupt_payload": interrupt_payload,
    }


def _start(
    document_text: str,
    filename: str,
    template_id: str,
    research_mode: str,
    ingestion: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    thread_id = _thread_id()
    initial_state = {
        "document_text": document_text,
        "filename": filename,
        "template_id": template_id,
        "research_mode": research_mode,
        "thread_id": thread_id,
        "status": "extracting",
    }
    if ingestion:
        initial_state["ingestion"] = ingestion
    HITL_GRAPH.invoke(initial_state, _config(thread_id))
    return _snapshot_payload(thread_id)


def hitl_start(document_text: str, filename: str = "pasted-requirements.txt", template_id: str = "starter", research_mode: str = "azure_official_only") -> Dict[str, Any]:
    return _start(document_text, filename, template_id, research_mode)


def hitl_start_from_upload(file_storage: Any, template_id: str = "starter", research_mode: str = "azure_official_only") -> Dict[str, Any]:
    ingestion = ingest_upload(file_storage)
    document_text = "\f".join(str(chunk.get("text") or "") for chunk in ingestion.get("chunks") or [])
    if not document_text.strip():
        raise ValueError("uploaded document contains no readable text")
    return _start(
        document_text,
        ingestion.get("filename") or "uploaded-document",
        template_id,
        research_mode,
        ingestion=ingestion,
    )


def hitl_resume(thread_id: str, response: Dict[str, Any]) -> Dict[str, Any]:
    HITL_GRAPH.invoke(Command(resume=response), _config(thread_id))
    return _snapshot_payload(thread_id)


def hitl_get_state(thread_id: str) -> Dict[str, Any]:
    return _snapshot_payload(thread_id)
