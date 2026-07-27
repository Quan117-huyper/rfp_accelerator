"""Run the published Foundry agents through the same LangGraph workflow as the app.

The script intentionally uses a fresh Python process so AzureCliCredential obtains
the active Azure CLI token.  It writes inspectable JSON artifacts under generated/
and never prints credentials.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from werkzeug.datastructures import FileStorage


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from hitl_graph import hitl_resume, hitl_start_from_upload  # noqa: E402
from ppt_renderer import render_pptx  # noqa: E402


RESULTS = ROOT / "generated" / "e2e-results"
FIXTURE = ROOT / "generated" / "test-fixtures" / "contoso_proposal_automation_rfp.docx"
TEMPLATE_ID = os.getenv("E2E_TEMPLATE_ID", "master_template")


def write_json(name: str, payload: object) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def state(snapshot: dict) -> dict:
    return snapshot.get("state") or {}


def _answer_requirement_question(question: dict) -> str:
    field = str(question.get("field") or "").lower()
    text = str(question.get("question") or "").lower()
    if "retention" in field or "retention" in text or "30 days" in text or "90 days" in text:
        return (
            "Retain uploaded customer source documents for 90 days for the POC. "
            "The 30-day deletion statement is treated as superseded by the later 90-day retention requirement."
        )
    if "availability" in field or "availability" in text or "sla" in text or "rpo" in text or "rto" in text:
        return (
            "Use a POC target of 99.5% service availability during Vietnam business hours, "
            "RPO 24 hours for workflow metadata, and RTO 4 hours. Production SLA will be finalized after UAT."
        )
    if "region" in field or "region" in text:
        return "Use Southeast Asia as the primary Azure region for the POC unless the customer tenant requires another approved region."
    if "cost" in field or "budget" in text or "usd" in text:
        return "Keep non-model Azure platform run cost below 250 USD per month for the POC; report Azure OpenAI token usage separately."
    if "sharepoint" in field or "graph" in text:
        return "Use read-only Microsoft Graph access to approved SharePoint project folders before UAT; generated PPTX files may be written back to the project folder."
    return (
        "Assume this is required for the POC, must preserve source traceability, and must remain inside the approved Azure and Microsoft 365 security boundary."
    )


def build_requirement_answer(requirement_interrupt: dict) -> dict:
    questions = requirement_interrupt.get("questions") or []
    clarifications = {}
    answered_questions = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        field = str(question.get("field") or question.get("id") or f"question_{len(answered_questions) + 1}")
        answer = _answer_requirement_question(question)
        clarifications[field] = answer
        answered_questions.append({
            "id": question.get("id"),
            "requirement_id": question.get("requirement_id"),
            "field": field,
            "question": question.get("question"),
            "answer": answer,
        })
    if not clarifications:
        clarifications["hitl_review"] = "No additional requirement clarification was requested by the Requirement Agent."

    additional_instruction = (
        "Treat all HITL clarification answers as authoritative. "
        "Do not send customer document content to public web search. "
        "Prefer a low-cost Azure POC architecture that can be upgraded for production availability later."
    )
    return {
        "decision": "approved",
        "clarifications": clarifications,
        "additional_instruction": additional_instruction,
        "answered_questions": answered_questions,
    }


def export_agent_outputs(requirement_state: dict, architecture_state: dict | None = None, completed_state: dict | None = None) -> None:
    write_json("01_requirement_agent_output.json", {
        "extraction": requirement_state.get("extraction") or {},
        "agent_requirements": requirement_state.get("agent_requirements") or {},
        "clarification_questions": requirement_state.get("clarification_questions") or [],
    })
    if architecture_state:
        research_result = architecture_state.get("research_result") or {}
        write_json("03_architect_agent_output.json", research_result.get("agent_output") or research_result)
    if completed_state:
        proposal = completed_state.get("proposal") or {}
        write_json("05_proposal_agent_output.json", proposal.get("proposal_agent_output") or proposal)
        write_json("06_pptagent_slide_plan.json", proposal.get("pptagent_input") or {})


def main() -> None:
    if not FIXTURE.exists():
        raise SystemExit(f"Fixture missing: {FIXTURE}. Run create_e2e_rfp_fixture.py first.")

    with FIXTURE.open("rb") as stream:
        requirement_checkpoint = hitl_start_from_upload(
            FileStorage(stream=stream, filename=FIXTURE.name),
            template_id=TEMPLATE_ID,
            research_mode="azure_official_only",
        )
    write_json("01_requirement_checkpoint.json", requirement_checkpoint)
    requirement_state = state(requirement_checkpoint)
    if requirement_state.get("status") != "awaiting_requirement_review":
        raise SystemExit(f"Requirement Agent did not reach HITL: {requirement_state.get('error')}")
    export_agent_outputs(requirement_state)

    thread_id = requirement_checkpoint["thread_id"]
    requirement_interrupt = requirement_checkpoint.get("interrupt_payload") or {}
    write_json("01_requirement_hitl.json", requirement_interrupt)

    requirement_answer = build_requirement_answer(requirement_interrupt)
    write_json("02_requirement_hitl_answer.json", requirement_answer)
    architecture_checkpoint = hitl_resume(thread_id, requirement_answer)
    write_json("03_architecture_checkpoint.json", architecture_checkpoint)
    architecture_state = state(architecture_checkpoint)
    if architecture_state.get("status") != "awaiting_architecture_approval":
        raise SystemExit(f"Architect Agent did not reach HITL: {architecture_state.get('error')}")
    export_agent_outputs(requirement_state, architecture_state)

    architecture_interrupt = architecture_checkpoint.get("interrupt_payload") or {}
    write_json("03_architecture_hitl.json", architecture_interrupt)
    architecture_answer = {
        "decision": "approved",
        "feedback": "",
        "cost_assumptions": architecture_state.get("cost_assumptions") or [],
    }
    write_json("04_architecture_hitl_answer.json", architecture_answer)
    completed = hitl_resume(thread_id, architecture_answer)
    write_json("05_proposal_checkpoint.json", completed)
    completed_state = state(completed)
    if completed_state.get("status") != "completed":
        raise SystemExit(f"Proposal Agent did not complete: {completed_state.get('error')}")
    export_agent_outputs(requirement_state, architecture_state, completed_state)

    pptx_path = render_pptx(completed_state["proposal"], TEMPLATE_ID)
    pptx_export = {
        "template_id": TEMPLATE_ID,
        "output_path": str(pptx_path),
        "filename": pptx_path.name,
        "bytes": pptx_path.stat().st_size,
    }
    write_json("07_pptx_export.json", pptx_export)

    summary = {
        "thread_id": thread_id,
        "template_id": TEMPLATE_ID,
        "requirement_runtime": (requirement_state.get("extraction") or {}).get("extraction_mode"),
        "requirement_count": sum(
            len(values) for values in ((requirement_state.get("extraction") or {}).get("extracted") or {}).values()
        ),
        "requirement_questions": len(requirement_interrupt.get("questions") or []),
        "requirement_answered_questions": len(requirement_answer.get("answered_questions") or []),
        "architect_runtime": (architecture_state.get("research_result") or {}).get("mode"),
        "architect_components": len(((architecture_state.get("research_result") or {}).get("architecture") or {}).get("components") or []),
        "architect_questions": len(architecture_interrupt.get("architecture", {}).get("clarification_questions") or []),
        "proposal_runtime": (completed_state.get("proposal") or {}).get("generation_mode"),
        "proposal_slides": len(((completed_state.get("proposal") or {}).get("pptagent_input") or {}).get("slides") or []),
        "pptx_export": pptx_export,
    }
    write_json("00_e2e_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
