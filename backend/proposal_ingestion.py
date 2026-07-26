"""Document ingestion for the proposal workflow.

The legacy accelerator chunker writes Azure Document Intelligence sections to Cosmos DB.
This module keeps the proposal POC self-contained and returns structured, traceable chunks
for downstream requirement extraction instead.
"""

from __future__ import annotations

import hashlib
import os
import re
from io import BytesIO
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_CHUNK_SIZE = 3500
DEFAULT_CHUNK_OVERLAP = 300
MIN_NATIVE_PAGE_CHARS = 80


def ingest_text(document_text: str, filename: str = "pasted-requirements.txt") -> Dict[str, Any]:
    pages = []
    for index, page_text in enumerate(document_text.replace("\r\n", "\n").split("\f"), start=1):
        clean = page_text.strip()
        if clean:
            pages.append({"page": index, "text": clean, "parser": "native"})
    return _build_ingestion(filename, pages, source_type="text")


def ingest_upload(file_storage) -> Dict[str, Any]:
    filename = file_storage.filename or "uploaded-document"
    raw = file_storage.read()
    lower_name = filename.lower()
    if lower_name.endswith((".txt", ".md")):
        return ingest_text(raw.decode("utf-8", errors="ignore"), filename)
    if lower_name.endswith(".docx"):
        return _build_ingestion(filename, _read_docx(raw), source_type="docx")
    if lower_name.endswith(".pdf"):
        return _build_ingestion(filename, _read_pdf(raw), source_type="pdf")
    raise ValueError("Supported upload formats are .txt, .md, .pdf, and .docx.")


def _read_docx(raw: bytes) -> List[Dict[str, Any]]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(BytesIO(raw))
    blocks: List[str] = []
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = Paragraph(child, document).text.strip()
            if text:
                blocks.append(text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            rows = []
            for row in table.rows:
                values = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(values):
                    rows.append(" | ".join(values))
            if rows:
                blocks.append("[Table]\n" + "\n".join(rows))
    text = "\n\n".join(blocks).strip()
    return [{"page": 1, "text": text, "parser": "native"}] if text else []


def _read_pdf(raw: bytes) -> List[Dict[str, Any]]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(raw))
    pages = [
        {"page": index, "text": (page.extract_text() or "").strip(), "parser": "native"}
        for index, page in enumerate(reader.pages, start=1)
    ]
    weak_page_numbers = [item["page"] for item in pages if len(_compact(item["text"])) < MIN_NATIVE_PAGE_CHARS]
    if weak_page_numbers:
        try:
            ocr_pages = _read_pdf_with_document_intelligence(raw)
            ocr_parser = "document_intelligence"
        except Exception:
            ocr_pages = _read_pdf_with_optional_paddle(raw, weak_page_numbers)
            ocr_parser = "paddle_ocr"
        for page in pages:
            replacement = ocr_pages.get(page["page"], "")
            if page["page"] in weak_page_numbers and replacement.strip():
                page["text"] = replacement.strip()
                page["parser"] = ocr_parser
    return [page for page in pages if page["text"]]


def _read_pdf_with_document_intelligence(raw: bytes) -> Dict[int, str]:
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or os.getenv("FORM_RECOGNIZER_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or os.getenv("FORM_RECOGNIZER_KEY")
    if not endpoint or not key:
        raise RuntimeError("Document Intelligence is not configured")

    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
    result = client.begin_analyze_document("prebuilt-layout", raw, content_type="application/pdf").result()
    content = getattr(result, "content", "") or ""
    pages: Dict[int, str] = {}
    for page in getattr(result, "pages", []) or []:
        spans = getattr(page, "spans", []) or []
        page_text = "".join(
            content[span.offset : span.offset + span.length] for span in spans
        ).strip()
        if page_text:
            pages[int(page.page_number)] = page_text

    for table in getattr(result, "tables", []) or []:
        regions = getattr(table, "bounding_regions", []) or []
        page_number = int(regions[0].page_number) if regions else None
        if not page_number:
            continue
        rows: Dict[int, List[str]] = {}
        for cell in getattr(table, "cells", []) or []:
            rows.setdefault(int(cell.row_index), []).append(str(cell.content or "").strip())
        table_text = "\n".join(" | ".join(values) for _, values in sorted(rows.items()) if any(values))
        if table_text:
            pages[page_number] = f"{pages.get(page_number, '')}\n[Table]\n{table_text}".strip()
    return pages


def _read_pdf_with_optional_paddle(raw: bytes, page_numbers: List[int]) -> Dict[int, str]:
    """Optional local fallback. Azure Document Intelligence remains the default OCR service."""
    if os.getenv("ENABLE_PADDLE_OCR", "false").lower() != "true":
        return {}
    try:
        import fitz
        from paddleocr import PaddleOCR
    except ImportError:
        return {}

    document = fitz.open(stream=raw, filetype="pdf")
    ocr = PaddleOCR(use_angle_cls=True, lang="en")
    pages: Dict[int, str] = {}
    for page_number in page_numbers:
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        result = ocr.ocr(pixmap.tobytes("png"), cls=True)
        lines = [line[1][0] for group in result or [] for line in group or []]
        if lines:
            pages[page_number] = "\n".join(lines)
    return pages


def _build_ingestion(filename: str, pages: List[Dict[str, Any]], source_type: str) -> Dict[str, Any]:
    raw_fingerprint = "\n".join(item["text"] for item in pages).encode("utf-8", errors="ignore")
    document_id = hashlib.sha1(raw_fingerprint).hexdigest()[:16]
    chunks = _hierarchical_chunks(document_id, pages)
    parser_counts: Dict[str, int] = {}
    for page in pages:
        parser_counts[page["parser"]] = parser_counts.get(page["parser"], 0) + 1
    return {
        "document_id": document_id,
        "filename": filename,
        "source_type": source_type,
        "chunks": chunks,
        "stats": {
            "pages": len(pages),
            "chunks": len(chunks),
            "parser_pages": parser_counts,
            "characters": sum(len(item["text"]) for item in pages),
        },
    }


def _hierarchical_chunks(document_id: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sections: List[Tuple[str, List[Tuple[int, str]]]] = []
    current_title = "Document Overview"
    current_items: List[Tuple[int, str]] = []

    def flush_section() -> None:
        nonlocal current_items
        if current_items:
            sections.append((current_title, current_items))
            current_items = []

    for page in pages:
        for block in _blocks(page["text"]):
            if _looks_like_heading(block):
                flush_section()
                current_title = block.strip("#: ")[:160]
            else:
                current_items.append((int(page["page"]), block))
    flush_section()

    chunks: List[Dict[str, Any]] = []
    for section_index, (section, items) in enumerate(sections, start=1):
        chunk_index = 1
        buffer: List[Tuple[int, str]] = []
        size = 0
        for page_number, block in items:
            if buffer and size + len(block) + 2 > DEFAULT_CHUNK_SIZE:
                chunks.append(_chunk_record(document_id, section, section_index, chunk_index, buffer))
                overlap_text = _tail_text(buffer, DEFAULT_CHUNK_OVERLAP)
                buffer = [(buffer[-1][0], overlap_text)] if overlap_text else []
                size = len(overlap_text)
                chunk_index += 1
            buffer.append((page_number, block))
            size += len(block) + 2
        if buffer:
            chunks.append(_chunk_record(document_id, section, section_index, chunk_index, buffer))
    return chunks


def _chunk_record(
    document_id: str, section: str, section_index: int, chunk_index: int, items: List[Tuple[int, str]]
) -> Dict[str, Any]:
    pages = [page for page, _ in items]
    return {
        "document_id": document_id,
        "chunk_id": f"{document_id}-s{section_index:02d}-c{chunk_index:03d}",
        "section": section,
        "page_start": min(pages),
        "page_end": max(pages),
        "text": "\n\n".join(text for _, text in items).strip(),
    }


def _blocks(text: str) -> Iterable[str]:
    for block in re.split(r"\n\s*\n", text):
        clean = re.sub(r"\s+", " ", block).strip()
        if clean:
            yield clean


def _looks_like_heading(text: str) -> bool:
    if len(text) > 120 or len(text.split()) > 14 or text.endswith((".", ";", "?")):
        return False
    return bool(re.match(r"^(\d+(?:\.\d+)*\s+|[A-Z][A-Z0-9 /&-]{5,}$|#{1,6}\s+)", text))


def _tail_text(items: List[Tuple[int, str]], limit: int) -> str:
    text = "\n\n".join(value for _, value in items)
    return text[-limit:].lstrip()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)
