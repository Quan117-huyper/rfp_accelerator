from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "generated" / "test-fixtures"
SCANNED_OUTPUT = OUTPUT_DIR / "scanned_rfp_ocr_case.pdf"
TABLE_OUTPUT = OUTPUT_DIR / "table_heavy_layout_case.pdf"


def create_scanned_pdf() -> None:
    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arial.ttf", 54)
        body_font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    draw.text((120, 100), "Scanned RFP - OCR Required", fill="black", font=title_font)
    lines = [
        "1 Scope",
        "The platform must extract requirements from scanned PDF RFP documents.",
        "Customer source files must be retained for 90 days.",
        "The system must preserve page references for every extracted requirement.",
        "",
        "Requirement ID | Category | Priority | Description",
        "REQ-001 | Functional | High | Upload scanned PDF documents",
        "REQ-002 | Security | High | Project-scoped access control",
        "REQ-003 | NFR | Medium | Process 100 pages within 10 minutes",
    ]
    y = 220
    for line in lines:
        draw.text((120, y), line, fill="black", font=body_font)
        y += 58

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    pdf = canvas.Canvas(str(SCANNED_OUTPUT), pagesize=letter)
    width, height = letter
    pdf.drawImage(ImageReader(buffer), 36, 36, width=width - 72, height=height - 72, preserveAspectRatio=True)
    pdf.showPage()
    pdf.save()


def create_table_heavy_pdf() -> None:
    pdf = canvas.Canvas(str(TABLE_OUTPUT), pagesize=letter)
    width, height = letter
    margin = 36
    top = height - 64
    row_height = 28
    columns = [margin, 126, 226, 316, width - margin]

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, height - 36, "Table Heavy RFP Layout Case")
    pdf.setFont("Helvetica", 9)

    headers = ["Req ID", "Category", "Priority", "Description"]
    rows = [
        [f"REQ-{index:03d}", "Functional" if index % 2 else "Security", "High", f"Preserve source traceability row {index}."]
        for index in range(1, 22)
    ]

    for row_index, values in enumerate([headers] + rows):
        y_top = top - row_index * row_height
        y_bottom = y_top - row_height
        pdf.setStrokeColor(colors.black)
        pdf.line(margin, y_top, width - margin, y_top)
        pdf.line(margin, y_bottom, width - margin, y_bottom)
        for x in columns:
            pdf.line(x, y_top, x, y_bottom)
        pdf.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 8)
        for col_index, value in enumerate(values):
            pdf.drawString(columns[col_index] + 4, y_bottom + 9, value[:48])

    pdf.showPage()
    pdf.save()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    create_scanned_pdf()
    create_table_heavy_pdf()
    print(SCANNED_OUTPUT)
    print(TABLE_OUTPUT)


if __name__ == "__main__":
    main()
