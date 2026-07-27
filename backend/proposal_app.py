import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from azure_runtime import load_azure_runtime_configuration
from deep_presenter_renderer import render_with_deep_presenter
from hitl_graph import hitl_get_state, hitl_resume, hitl_start, hitl_start_from_upload
from ppt_renderer import list_templates, render_pptx
from proposal_ingestion import ingest_text, ingest_upload
from proposal_agent import analyze_document, generate_proposal, read_uploaded_text, research_architecture


load_dotenv(Path(__file__).resolve().parent.parent / ".env")
AZURE_RUNTIME = load_azure_runtime_configuration()

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "proposal-generation-agent",
            "azure": {
                "foundry_project_endpoint_configured": bool(os.getenv("FOUNDRY_PROJECT_ENDPOINT")),
                "search_endpoint_configured": bool(os.getenv("AZURE_SEARCH_ENDPOINT")),
                "document_intelligence_endpoint_configured": bool(
                    os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
                    or os.getenv("FORM_RECOGNIZER_ENDPOINT")
                ),
                "key_vault": AZURE_RUNTIME["key_vault"],
            },
        }
    )


@app.route("/proposal/templates", methods=["GET"])
def templates():
    return jsonify({"templates": list_templates()})


@app.route("/proposal/hitl/start", methods=["POST"])
def hitl_start_route():
    data = request.get_json(silent=True) or {}
    document_text = str(data.get("document_text") or "").strip()
    if not document_text:
        return jsonify({"error": "document_text is required"}), 400
    try:
        result = hitl_start(
            document_text,
            filename=str(data.get("filename") or "pasted-requirements.txt"),
            template_id=str(data.get("template_id") or "starter"),
            research_mode=str(data.get("research_mode") or "azure_official_only"),
        )
        if result.get("state", {}).get("status") == "failed":
            return jsonify(result), 503
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/proposal/hitl/start-upload", methods=["POST"])
def hitl_start_upload_route():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    try:
        result = hitl_start_from_upload(
            request.files["file"],
            template_id=str(request.form.get("template_id") or "starter"),
            research_mode=str(request.form.get("research_mode") or "azure_official_only"),
        )
        if result.get("state", {}).get("status") == "failed":
            return jsonify(result), 503
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/proposal/hitl/<thread_id>/resume", methods=["POST"])
def hitl_resume_route(thread_id):
    data = request.get_json(silent=True) or {}
    try:
        result = hitl_resume(thread_id, data)
        if result.get("state", {}).get("status") == "failed":
            return jsonify(result), 503
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc), "thread_id": thread_id}), 400


@app.route("/proposal/hitl/<thread_id>", methods=["GET"])
def hitl_state_route(thread_id):
    result = hitl_get_state(thread_id)
    if not result.get("state"):
        return jsonify({"error": "HITL thread not found", "thread_id": thread_id}), 404
    return jsonify(result)


@app.route("/proposal/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    document_text = data.get("document_text", "").strip()
    clarifications = data.get("clarifications", {})

    if not document_text:
        return jsonify({"error": "document_text is required"}), 400

    result = analyze_document(ingest_text(document_text), clarifications)
    if result.get("extraction_mode") in {"failed", "unavailable"}:
        return jsonify({"error": result.get("provider_errors", ["Requirement Agent failed"])[0]}), 503
    return jsonify(result)


@app.route("/proposal/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    try:
        result = analyze_document(ingest_upload(request.files["file"]))
        if result.get("extraction_mode") in {"failed", "unavailable"}:
            return jsonify({"error": result.get("provider_errors", ["Requirement Agent failed"])[0]}), 503
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/proposal/reference-upload", methods=["POST"])
def upload_reference():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    try:
        file_storage = request.files["file"]
        text = read_uploaded_text(file_storage).strip()
        if not text:
            return jsonify({"error": "reference document contains no readable text"}), 400
        return jsonify(
            {
                "reference": {
                    "document_name": file_storage.filename or "reference-document",
                    "excerpt": text[:12000],
                }
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/proposal/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    extracted = data.get("extracted")
    clarifications = data.get("clarifications", {})
    architecture_decisions = data.get("architecture_decisions")
    cost_assumptions = data.get("cost_assumptions", [])
    template_id = data.get("template_id", "starter")
    architecture_approved = data.get("architecture_approved") is True
    if not extracted:
        return jsonify({"error": "extracted requirements are required"}), 400
    if not architecture_approved:
        return jsonify({"error": "solution architect approval is required before proposal generation"}), 409
    return jsonify({
        "proposal": generate_proposal(
            extracted,
            clarifications,
            architecture_decisions,
            cost_assumptions,
            template_id,
            architecture_approved,
        )
    })


@app.route("/proposal/research", methods=["POST"])
def research():
    data = request.get_json(silent=True) or {}
    extracted = data.get("extracted")
    clarifications = data.get("clarifications", {})
    research_mode = data.get("research_mode", "azure_official_only")
    project_context = data.get("project_context", {})
    private_references = data.get("private_references", [])
    agent_requirements = data.get("agent_requirements")
    if not extracted:
        return jsonify({"error": "extracted requirements are required"}), 400

    result = research_architecture(
        extracted, clarifications, research_mode, project_context, private_references, agent_requirements
    )
    if result.get("mode") in {"failed", "unavailable"}:
        return jsonify(result), 503
    return jsonify(result)


@app.route("/proposal/export-pptx", methods=["POST"])
def export_pptx():
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal")
    template_id = data.get("template_id", "starter")
    presentation_pipeline = str(data.get("presentation_pipeline") or "starter_renderer")
    if not proposal:
        return jsonify({"error": "proposal is required"}), 400
    if proposal.get("architecture_approved") is not True:
        return jsonify({"error": "solution architect approval is required before PPTX export"}), 409

    try:
        if presentation_pipeline == "deep_presenter":
            output_path = render_with_deep_presenter(proposal, template_id)
        elif presentation_pipeline == "master_template":
            output_path = render_pptx(proposal, "master_template")
        else:
            output_path = render_pptx(proposal, template_id)
        return jsonify(
            {
                "message": "PowerPoint generated",
                "filename": output_path.name,
                "presentation_pipeline": presentation_pipeline,
                "download_url": f"{request.host_url.rstrip('/')}/proposal/download/{output_path.name}",
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/proposal/download/<path:filename>", methods=["GET"])
def download(filename):
    output_path = Path(__file__).resolve().parent.parent / "generated" / filename
    if not output_path.exists():
        return jsonify({"error": "file not found"}), 404
    return send_file(
        output_path,
        as_attachment=True,
        download_name=output_path.name,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the proposal generation backend.")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    args = parser.parse_args()
    app.run(debug=False, threaded=True, port=args.port)
