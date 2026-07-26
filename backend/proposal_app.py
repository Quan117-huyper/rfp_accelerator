from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from ppt_renderer import list_templates, render_pptx
from proposal_agent import analyze_document, generate_proposal, read_uploaded_text


load_dotenv()

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "proposal-generation-agent"})


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

    return jsonify(analyze_document(document_text, clarifications))


@app.route("/proposal/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    try:
        document_text = read_uploaded_text(request.files["file"])
        return jsonify(analyze_document(document_text))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/proposal/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    extracted = data.get("extracted")
    clarifications = data.get("clarifications", {})
    if not extracted:
        return jsonify({"error": "extracted requirements are required"}), 400
    return jsonify({"proposal": generate_proposal(extracted, clarifications)})


@app.route("/proposal/export-pptx", methods=["POST"])
def export_pptx():
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal")
    template_id = data.get("template_id", "starter")
    if not proposal:
        return jsonify({"error": "proposal is required"}), 400

    try:
        output_path = render_pptx(proposal, template_id)
        return jsonify(
            {
                "message": "PowerPoint generated",
                "filename": output_path.name,
                "download_url": f"http://localhost:5000/proposal/download/{output_path.name}",
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
    app.run(debug=True, threaded=True, port=5000)
