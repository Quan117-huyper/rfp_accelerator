import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from azure_runtime import load_azure_runtime_configuration
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


@app.route("/proposal/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    document_text = data.get("document_text", "").strip()
    clarifications = data.get("clarifications", {})

    if not document_text:
        return jsonify({"error": "document_text is required"}), 400

    return jsonify(analyze_document(ingest_text(document_text), clarifications))


@app.route("/proposal/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    try:
        return jsonify(analyze_document(ingest_upload(request.files["file"])))
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
    if not extracted:
        return jsonify({"error": "extracted requirements are required"}), 400

    result = research_architecture(
        extracted, clarifications, research_mode, project_context, private_references
    )
    if result.get("mode") in {"failed", "unavailable"}:
        return jsonify(result), 503
    return jsonify(result)


@app.route("/proposal/export-pptx", methods=["POST"])
def export_pptx():
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal")
    template_id = data.get("template_id", "starter")
    if not proposal:
        return jsonify({"error": "proposal is required"}), 400
    if proposal.get("architecture_approved") is not True:
        return jsonify({"error": "solution architect approval is required before PPTX export"}), 409

    try:
        output_path = render_pptx(proposal, template_id)
        return jsonify(
            {
                "message": "PowerPoint generated",
                "filename": output_path.name,
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
    app.run(debug=False, threaded=True, port=int(os.getenv("PORT", "5000")))
