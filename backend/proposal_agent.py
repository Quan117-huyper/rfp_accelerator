import json
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


REQUIREMENT_FIELDS = [
    "business_goals",
    "functional_requirements",
    "non_functional_requirements",
    "constraints",
    "assumptions",
    "integrations",
    "security_needs",
    "expected_users",
]


FIELD_QUALITY_GUIDE = {
    "business_goals": "Clear target business outcomes, measurable success criteria, and the main pain points being solved.",
    "functional_requirements": "User-visible capabilities, workflows, data operations, and acceptance behavior.",
    "non_functional_requirements": "Scale, latency, availability, performance, compliance, observability, and maintainability.",
    "constraints": "Budget, timeline, hosting, technology, data residency, security, procurement, or policy limits.",
    "assumptions": "Explicit decisions used when the source document is silent or ambiguous.",
    "integrations": "Identity providers, data sources, APIs, enterprise systems, and downstream channels.",
    "security_needs": "Authentication, authorization, RBAC, encryption, audit, private networking, and data leakage controls.",
    "expected_users": "User personas, user count, concurrency, roles, and access boundaries.",
}


AI_PATTERN_KB = [
    {
        "name": "RAG with metadata filtering",
        "purpose": "Answer questions over enterprise documents while enforcing document-level and user-level filters.",
        "use_when": "Knowledge is mostly unstructured documents and answers must cite source material.",
        "data": "PDF, Word, HTML, wiki pages, tickets, policies, manuals.",
    },
    {
        "name": "Knowledge graph",
        "purpose": "Represent relationships between entities, policies, products, systems, and decisions.",
        "use_when": "The solution depends on multi-hop reasoning or explainable entity relationships.",
        "data": "Structured master data, taxonomies, relationship-heavy documents, CMDB, CRM, ERP metadata.",
    },
    {
        "name": "Multi-agent orchestration",
        "purpose": "Split work across specialist agents for research, extraction, validation, architecture, and writing.",
        "use_when": "The workflow has multiple reviewable stages and benefits from tool-using specialists.",
        "data": "Mixed documents, web sources, templates, cost tables, architecture inventories.",
    },
    {
        "name": "Computer-use automation",
        "purpose": "Operate legacy user interfaces when no stable API exists.",
        "use_when": "The process requires repetitive work in desktop or web applications that cannot be integrated directly.",
        "data": "Screens, forms, exported files, application UI state.",
    },
    {
        "name": "Workflow automation",
        "purpose": "Coordinate deterministic approvals, notifications, data movement, and business rules.",
        "use_when": "The solution needs reliable handoffs between people, systems, and scheduled jobs.",
        "data": "Events, forms, APIs, queues, business process states.",
    },
]


ARCHITECTURE_STACK = [
    "Gemini API or local LLM fallback for extraction and drafting",
    "FAISS, Chroma, or pgvector for retrieval over proposal documents",
    "Local disk or S3-compatible storage for uploads and generated PPTX files",
    "PostgreSQL for projects, reviews, and version history",
    "Optional Tavily or SerpAPI research tools when external evidence is needed",
    "Queue or background worker for long-running document jobs",
    "PowerPoint template renderer for branded enterprise decks",
    "Application telemetry and logging for quality and traceability",
]


def _gemini_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _extract_with_gemini(document_text: str, prompt: str) -> Dict[str, Any]:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"{prompt}\n\nCustomer document:\n{document_text[:45000]}",
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Gemini API error {exc.code}: {detail}") from exc

    candidates = raw.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini API returned no candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    return _extract_json_object(text)


def _sentences_with_keywords(text: str, keywords: List[str]) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    matches = []
    for sentence in sentences:
        clean = sentence.strip(" -\t\r")
        if clean and any(keyword.lower() in clean.lower() for keyword in keywords):
            matches.append(clean)
    return matches[:8]


def fallback_extract_requirements(document_text: str) -> Dict[str, List[str]]:
    text = document_text.strip()
    extracted = {
        "business_goals": _sentences_with_keywords(
            text, ["goal", "objective", "purpose", "business", "improve", "reduce", "increase", "optimize"]
        ),
        "functional_requirements": _sentences_with_keywords(
            text, ["must", "shall", "can", "user", "upload", "answer", "generate", "integrate", "workflow"]
        ),
        "non_functional_requirements": _sentences_with_keywords(
            text, ["scale", "latency", "performance", "availability", "monitoring", "cost", "maintainability"]
        ),
        "constraints": _sentences_with_keywords(
            text, ["constraint", "budget", "timeline", "deadline", "region", "policy"]
        ),
        "assumptions": [
            "The document is readable in supported formats or can be converted from text extraction.",
            "Human review is required before final proposal export.",
            "The proposal can be generated from a single prompt pass plus review refinements.",
        ],
        "integrations": _sentences_with_keywords(
            text, ["integrate", "identity", "SSO", "API", "CRM", "ERP", "SharePoint", "Teams", "database"]
        ),
        "security_needs": _sentences_with_keywords(
            text, ["security", "RBAC", "role", "access", "encrypt", "audit", "private", "compliance"]
        ),
        "expected_users": _sentences_with_keywords(
            text, ["user", "employee", "admin", "architect", "thousand", "concurrent", "role"]
        ),
    }

    for field in REQUIREMENT_FIELDS:
        if not extracted[field]:
            extracted[field] = []
    return extracted


def extract_requirements(document_text: str) -> Dict[str, Any]:
    prompt = f"""
You are a senior AI solution architect. Extract customer requirements from the document.
Return valid JSON only with:
{{
  "extracted": {{
    "business_goals": [],
    "functional_requirements": [],
    "non_functional_requirements": [],
    "constraints": [],
    "assumptions": [],
    "integrations": [],
    "security_needs": [],
    "expected_users": []
  }},
  "quality_notes": {{"field": "short assessment"}}
}}

Quality guide:
{json.dumps(FIELD_QUALITY_GUIDE, indent=2)}
"""

    if _gemini_available():
        try:
            parsed = _extract_with_gemini(document_text, prompt)
            return {"mode": "gemini", **parsed, "quality_guide": FIELD_QUALITY_GUIDE}
        except Exception as exc:
            return {
                "mode": "fallback",
                "provider_error": str(exc),
                "extracted": fallback_extract_requirements(document_text),
                "quality_guide": FIELD_QUALITY_GUIDE,
            }

    return {
        "mode": "fallback",
        "extracted": fallback_extract_requirements(document_text),
        "quality_guide": FIELD_QUALITY_GUIDE,
    }


def build_clarification_questions(extracted: Dict[str, List[str]]) -> List[Dict[str, str]]:
    questions = []
    checks = [
        ("business_goals", "What business outcomes or KPIs should this proposal optimize for?"),
        ("expected_users", "How many users, roles, and concurrent sessions should the solution support?"),
        ("security_needs", "What identity provider, RBAC model, audit, and data isolation requirements are mandatory?"),
        ("integrations", "Which enterprise systems or document repositories must be integrated first?"),
        ("non_functional_requirements", "What are the target availability, latency, retention, and monitoring requirements?"),
        ("constraints", "Are there fixed budget, timeline, region, data residency, or technology constraints?"),
    ]
    for field, question in checks:
        values = extracted.get(field, [])
        if not values:
            questions.append(
                {
                    "field": field,
                    "question": question,
                    "reason": FIELD_QUALITY_GUIDE[field],
                }
            )
    return questions


def recommend_patterns(extracted: Dict[str, List[str]]) -> List[Dict[str, str]]:
    text = " ".join(" ".join(v) for v in extracted.values()).lower()
    recommendations = []
    for pattern in AI_PATTERN_KB:
        name = pattern["name"].lower()
        include = (
            ("document" in text and "rag" in name)
            or ("role" in text and "rag" in name)
            or ("workflow" in text and "workflow" in name)
            or ("agent" in text and "agent" in name)
            or ("legacy" in text and "computer-use" in name)
            or ("relationship" in text and "graph" in name)
        )
        if include:
            recommendations.append(pattern)
    return recommendations or [AI_PATTERN_KB[0], AI_PATTERN_KB[4]]


def generate_proposal(extracted: Dict[str, List[str]], clarifications: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    clarifications = clarifications or {}
    patterns = recommend_patterns(extracted)
    expected_output = [
        "Extract the key requirements from the uploaded document.",
        "Ask clarification questions when security, scale, user roles, data source, or integration details are missing.",
        "Propose an implementable AI architecture and deployment design.",
        "Estimate costs for Development, Test, and UAT or Staging environments.",
        "Export a customer-ready PowerPoint proposal using the selected enterprise template while preserving branding.",
    ]
    key_engineering_challenges = [
        "Understanding unstructured requirement documents accurately.",
        "Avoiding generic, shallow, or hallucinated solution recommendations.",
        "Keeping the proposal consistent across business solution, technical architecture, infrastructure, and cost estimation.",
        "Mapping AI-generated content into PowerPoint templates without breaking the design.",
        "Supporting multiple proposal templates and future template changes.",
        "Creating a useful HITL loop so users can refine assumptions, solution direction, architecture, and final slide content.",
    ]

    return {
        "proposal_id": str(uuid.uuid4()),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "executive_summary": (
            "Build a secure AI Solution Architect proposal-generation agent that ingests customer requirement "
            "documents, extracts structured requirements, asks targeted clarification questions, recommends an "
            "implementable solution architecture, and exports a customer-ready PowerPoint using enterprise templates."
        ),
        "problem_statement": (
            "Proposal teams need to convert long, unstructured requirement documents into consistent business, "
            "technical, architecture, cost, risk, and assumption content without breaking approved presentation branding."
        ),
        "expected_output": expected_output,
        "key_engineering_challenges": key_engineering_challenges,
        "business_solution": [
            "Document intake with OCR/layout parsing and hierarchical chunking for long documents.",
            "Structured requirement extraction against a field-quality knowledge base.",
            "Human-in-the-loop clarification before final architecture and proposal writing.",
            "Reviewable proposal sections before PPTX export.",
            "Template abstraction layer for future slide templates.",
        ],
        "technical_solution": [
            "Ingestion service parses Word, PDF, text, and scanned content into normalized document sections.",
            "Extraction agent produces JSON for business goals, functional and non-functional requirements, constraints, assumptions, integrations, security needs, and expected users.",
            "Solution architect agent selects AI patterns from a controlled pattern knowledge base.",
            "Proposal composer generates section-specific content and validates consistency across architecture, cost, risks, and assumptions.",
            "PPT renderer applies template mappings and only updates intended placeholders.",
        ],
        "recommended_patterns": patterns,
        "architecture_stack": ARCHITECTURE_STACK,
        "infrastructure_design": [
            "Containerized API hosts the proposal workflow and worker tasks.",
            "A vector database stores document chunks and metadata for retrieval.",
            "Object storage keeps source documents, OCR artifacts, and generated proposal files.",
            "PostgreSQL stores project metadata, version history, and review state.",
            "A secrets manager protects API keys and connection strings.",
            "A queue or job runner coordinates parsing, extraction, review, and PPT export jobs.",
            "Application telemetry tracks latency, token usage, failures, and proposal-generation quality signals.",
        ],
        "cost_estimation": [
            {"environment": "Development", "monthly_estimate_usd": "50-250", "notes": "Small compute, local storage, and capped model usage."},
            {"environment": "Test", "monthly_estimate_usd": "150-700", "notes": "Representative data volume, integration testing, and scheduled load tests."},
            {"environment": "UAT/Staging", "monthly_estimate_usd": "400-1,500", "notes": "Production-like monitoring, backups, and larger model usage."},
        ],
        "implementation_approach": [
            "Phase 1: Template inventory, schema mapping, document ingestion MVP.",
            "Phase 2: Extraction, HITL clarification, solution-pattern recommendation.",
            "Phase 3: Proposal composer, consistency checks, cost model, PPTX export.",
            "Phase 4: Hardening, monitoring, UAT, and rollout.",
        ],
        "risks": [
            "Poor source document quality may reduce extraction accuracy; mitigate with OCR/layout confidence checks and reviewer approval.",
            "Template drift may break mappings; mitigate with template schema validation and visual regression checks.",
            "Generic architecture output may reduce trust; mitigate with controlled pattern KB and required assumptions.",
            "Cost estimates can vary with token volume and document count; mitigate with usage telemetry and environment budgets.",
        ],
        "assumptions": extracted.get("assumptions", []) + list(clarifications.values()),
        "delivery_notes": [
            "Use a branded enterprise template when available; fall back to the starter deck when no template is configured.",
            "Keep slide copy concise and audience-facing so the output reads like a real proposal.",
            "Prefer cloud-neutral wording unless a customer explicitly asks for a vendor-specific deployment.",
        ],
        "extracted_requirements": extracted,
    }


def analyze_document(document_text: str, clarifications: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    extraction = extract_requirements(document_text)
    extracted = extraction.get("extracted", {})
    questions = build_clarification_questions(extracted)
    proposal = generate_proposal(extracted, clarifications)
    return {
        "extraction_mode": extraction.get("mode", "llm"),
        "extracted": extracted,
        "quality_guide": extraction.get("quality_guide", FIELD_QUALITY_GUIDE),
        "clarification_questions": questions,
        "proposal": proposal,
    }


def read_uploaded_text(file_storage) -> str:
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if filename.endswith(".txt") or filename.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")
    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            from io import BytesIO

            reader = PdfReader(BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError(f"PDF parsing failed. Use OCR or a text-based PDF. {exc}")
    if filename.endswith(".docx"):
        try:
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(raw))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
        except Exception as exc:
            raise ValueError(f"DOCX parsing failed. {exc}")
    raise ValueError("Supported upload formats for the lightweight demo are .txt, .md, .pdf, and .docx.")


def proposal_output_dir() -> Path:
    output_dir = Path(__file__).resolve().parent.parent / "generated"
    output_dir.mkdir(exist_ok=True)
    return output_dir
