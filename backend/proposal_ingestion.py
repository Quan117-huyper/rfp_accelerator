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
from typing import Any, Dict, Iterable, List, Optional, Tuple


WHOLE_DOCUMENT_LIMIT_TOKENS = 40_000
CHUNK_TARGET_TOKENS = 32_000
CHUNK_MAX_TOKENS = 40_000
CHUNK_OVERLAP_TOKENS = 300
MIN_NATIVE_PAGE_CHARS = 80
MIN_NATIVE_PAGE_QUALITY_CHARS = 250
MIN_NATIVE_PAGE_WORDS = 40
MAX_GARBLED_RATIO = 0.08
IMAGE_HEAVY_TEXT_LIMIT = 800
TABLE_DRAWING_THRESHOLD = 30
COMPLEX_LAYOUT_DRAWING_THRESHOLD = 120
TABLE_TEXT_LINE_THRESHOLD = 6


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
        {
            "page": index,
            "text": (page.extract_text() or "").strip(),
            "parser": "native",
            "quality": _pdf_page_quality(page, (page.extract_text() or "").strip()),
        }
        for index, page in enumerate(reader.pages, start=1)
    ]
    weak_page_numbers = [item["page"] for item in pages if item["quality"]["needs_document_intelligence"]]
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
                if ocr_parser == "document_intelligence":
                    page["parser"] = "document_intelligence_layout" if page["quality"]["reason"] == "layout_risk" else "document_intelligence_ocr"
                else:
                    page["parser"] = ocr_parser

        unresolved = [
            str(page_number)
            for page_number in weak_page_numbers
            if not next((item["text"] for item in pages if item["page"] == page_number), "").strip()
        ]
        if unresolved:
            raise ValueError(
                "PDF page(s) "
                + ", ".join(unresolved)
                + " require OCR, but Azure Document Intelligence did not return readable content. "
                + "Check the Document Intelligence endpoint/key or upload a text-based PDF."
            )
    return [page for page in pages if page["text"]]


def _pdf_page_quality(page: Any, text: str) -> Dict[str, Any]:
    compact = _compact(text)
    word_count = len(re.findall(r"\w+", text, flags=re.UNICODE))
    image_count = _pdf_image_count(page)
    drawing_count = _pdf_drawing_operator_count(page)
    table_like_lines = _table_like_line_count(text)
    garbled_ratio = _garbled_ratio(text)

    if len(compact) < MIN_NATIVE_PAGE_CHARS:
        return {
            "needs_document_intelligence": True,
            "reason": "empty_or_scanned",
            "native_chars": len(compact),
            "native_words": word_count,
            "image_count": image_count,
            "drawing_count": drawing_count,
            "table_like_lines": table_like_lines,
            "garbled_ratio": garbled_ratio,
        }
    if len(compact) < MIN_NATIVE_PAGE_QUALITY_CHARS or word_count < MIN_NATIVE_PAGE_WORDS:
        reason = "image_heavy" if image_count else "weak_native_text"
        return {
            "needs_document_intelligence": True,
            "reason": reason,
            "native_chars": len(compact),
            "native_words": word_count,
            "image_count": image_count,
            "drawing_count": drawing_count,
            "table_like_lines": table_like_lines,
            "garbled_ratio": garbled_ratio,
        }
    if image_count >= 1 and len(compact) < IMAGE_HEAVY_TEXT_LIMIT:
        return {
            "needs_document_intelligence": True,
            "reason": "image_heavy",
            "native_chars": len(compact),
            "native_words": word_count,
            "image_count": image_count,
            "drawing_count": drawing_count,
            "table_like_lines": table_like_lines,
            "garbled_ratio": garbled_ratio,
        }
    if garbled_ratio > MAX_GARBLED_RATIO:
        return {
            "needs_document_intelligence": True,
            "reason": "layout_risk",
            "native_chars": len(compact),
            "native_words": word_count,
            "image_count": image_count,
            "drawing_count": drawing_count,
            "table_like_lines": table_like_lines,
            "garbled_ratio": garbled_ratio,
        }
    if drawing_count >= TABLE_DRAWING_THRESHOLD and table_like_lines >= TABLE_TEXT_LINE_THRESHOLD:
        return {
            "needs_document_intelligence": True,
            "reason": "layout_risk",
            "native_chars": len(compact),
            "native_words": word_count,
            "image_count": image_count,
            "drawing_count": drawing_count,
            "table_like_lines": table_like_lines,
            "garbled_ratio": garbled_ratio,
        }
    if drawing_count >= COMPLEX_LAYOUT_DRAWING_THRESHOLD and word_count >= MIN_NATIVE_PAGE_WORDS:
        return {
            "needs_document_intelligence": True,
            "reason": "layout_risk",
            "native_chars": len(compact),
            "native_words": word_count,
            "image_count": image_count,
            "drawing_count": drawing_count,
            "table_like_lines": table_like_lines,
            "garbled_ratio": garbled_ratio,
        }
    return {
        "needs_document_intelligence": False,
        "reason": "native_ok",
        "native_chars": len(compact),
        "native_words": word_count,
        "image_count": image_count,
        "drawing_count": drawing_count,
        "table_like_lines": table_like_lines,
        "garbled_ratio": garbled_ratio,
    }


def _pdf_image_count(page: Any) -> int:
    try:
        return len(getattr(page, "images", []) or [])
    except Exception:
        return 0


def _pdf_drawing_operator_count(page: Any) -> int:
    try:
        contents = page.get_contents()
        if contents is None:
            return 0
        streams = contents if isinstance(contents, list) else [contents]
        raw = b"".join(stream.get_data() for stream in streams if hasattr(stream, "get_data"))
    except Exception:
        return 0
    return sum(raw.count(operator) for operator in (b" re", b" l", b" m", b" S", b" s"))


def _table_like_line_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        if line.count("|") >= 2 or len(re.split(r"\s{2,}", line.strip())) >= 3:
            count += 1
    return count


def _garbled_ratio(text: str) -> float:
    if not text:
        return 0.0
    suspicious = sum(1 for char in text if char == "\ufffd" or ord(char) < 32 and char not in "\n\r\t")
    suspicious += text.count("�") + text.count("□")
    return suspicious / max(1, len(text))


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
    estimated_tokens = estimate_tokens(raw_fingerprint.decode("utf-8", errors="ignore"))
    extraction_mode = choose_mode(estimated_tokens)
    chunks = _hierarchical_chunks(document_id, pages, extraction_mode)
    parser_counts: Dict[str, int] = {}
    for page in pages:
        parser_counts[page["parser"]] = parser_counts.get(page["parser"], 0) + 1
    quality_pages = [page.get("quality") for page in pages if page.get("quality")]
    return {
        "document_id": document_id,
        "filename": filename,
        "source_type": source_type,
        "chunks": chunks,
        "stats": {
            "pages": len(pages),
            "chunks": len(chunks),
            "parser_pages": parser_counts,
            "document_intelligence_pages": sum(
                count for parser, count in parser_counts.items() if str(parser).startswith("document_intelligence")
            ),
            "page_quality": quality_pages,
            "characters": sum(len(item["text"]) for item in pages),
            "estimated_tokens": estimated_tokens,
            "extraction_mode": extraction_mode,
        },
    }


def estimate_tokens(text: str) -> int:
    """Fast token estimate used only to choose orchestration mode before agent calls."""
    words = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, int(len(words) * 1.3)) if text.strip() else 0


def choose_mode(estimated_tokens: int) -> str:
    return "whole_document" if estimated_tokens <= WHOLE_DOCUMENT_LIMIT_TOKENS else "chunked"


def _hierarchical_chunks(document_id: str, pages: List[Dict[str, Any]], extraction_mode: Optional[str] = None) -> List[Dict[str, Any]]:
    if extraction_mode is None:
        extraction_mode = choose_mode(estimate_tokens("\n".join(item["text"] for item in pages)))
    if extraction_mode == "whole_document":
        items = [(int(page["page"]), str(page["text"])) for page in pages if str(page.get("text") or "").strip()]
        return [_chunk_record(document_id, "Whole Document", [], 1, 1, items)] if items else []

    sections = _document_sections(pages)
    return _pack_sections(document_id, sections)


def _document_sections(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    current_title = "Document Overview"
    current_path: List[str] = []
    current_items: List[Tuple[int, str]] = []

    def flush_section() -> None:
        nonlocal current_items
        if current_items:
            text = "\n\n".join(value for _, value in current_items)
            sections.append(
                {
                    "section": current_title,
                    "heading_path": current_path[:] or [current_title],
                    "items": current_items,
                    "tokens": estimate_tokens(text),
                }
            )
            current_items = []

    for page in pages:
        for block in _blocks(page["text"]):
            heading = _heading_info(block)
            if heading:
                flush_section()
                current_title = heading["title"]
                current_path = _update_heading_path(current_path, heading["level"], current_title)
            else:
                current_items.append((int(page["page"]), block))
    flush_section()
    return sections


def _pack_sections(document_id: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    current_sections: List[Dict[str, Any]] = []
    current_tokens = 0
    section_index = 1

    def flush_current() -> None:
        nonlocal current_sections, current_tokens, section_index
        if not current_sections:
            return
        chunks.append(_chunk_from_sections(document_id, section_index, len(chunks) + 1, current_sections))
        section_index += 1
        current_sections = []
        current_tokens = 0

    for section in sections:
        section_tokens = int(section.get("tokens") or 0)
        if section_tokens > CHUNK_MAX_TOKENS:
            flush_current()
            chunks.extend(_split_large_section(document_id, section, section_index))
            section_index += 1
            continue

        if current_tokens + section_tokens <= CHUNK_TARGET_TOKENS:
            current_sections.append(section)
            current_tokens += section_tokens
            continue

        if current_sections and current_tokens + section_tokens <= CHUNK_MAX_TOKENS:
            current_sections.append(section)
            flush_current()
            continue

        flush_current()
        current_sections.append(section)
        current_tokens = section_tokens

    flush_current()
    return chunks


def _chunk_from_sections(
    document_id: str, section_index: int, chunk_index: int, sections: List[Dict[str, Any]]
) -> Dict[str, Any]:
    items: List[Tuple[int, str]] = []
    titles = []
    heading_paths = []
    for section in sections:
        title = str(section.get("section") or "Document Section")
        titles.append(title)
        heading_paths.append(section.get("heading_path") or [title])
        items.extend(section.get("items") or [])
    section_name = titles[0] if len(titles) == 1 else f"{titles[0]} through {titles[-1]}"
    return _chunk_record(document_id, section_name, heading_paths, section_index, chunk_index, items)


def _split_large_section(document_id: str, section: Dict[str, Any], section_index: int) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    buffer: List[Tuple[int, str]] = []
    buffer_tokens = 0
    chunk_index = 1
    for page_number, block in section.get("items") or []:
        block_tokens = estimate_tokens(block)
        if block_tokens > CHUNK_MAX_TOKENS:
            if buffer:
                chunks.append(_chunk_record(document_id, str(section["section"]), [section.get("heading_path") or []], section_index, chunk_index, buffer))
                chunk_index += 1
                buffer = []
                buffer_tokens = 0
            for part in _split_text_by_token_budget(block):
                chunks.append(
                    _chunk_record(
                        document_id,
                        str(section["section"]),
                        [section.get("heading_path") or []],
                        section_index,
                        chunk_index,
                        [(int(page_number), part)],
                    )
                )
                chunk_index += 1
            continue

        if buffer and buffer_tokens + block_tokens > CHUNK_MAX_TOKENS:
            chunks.append(_chunk_record(document_id, str(section["section"]), [section.get("heading_path") or []], section_index, chunk_index, buffer))
            overlap = _tail_tokens(buffer, CHUNK_OVERLAP_TOKENS)
            buffer = [(buffer[-1][0], overlap)] if overlap else []
            buffer_tokens = estimate_tokens(overlap)
            chunk_index += 1

        buffer.append((int(page_number), block))
        buffer_tokens += block_tokens

    if buffer:
        chunks.append(_chunk_record(document_id, str(section["section"]), [section.get("heading_path") or []], section_index, chunk_index, buffer))
    return chunks


def _split_text_by_token_budget(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.;:!?])\s+", text)
    parts: List[str] = []
    buffer: List[str] = []
    tokens = 0
    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        if buffer and tokens + sentence_tokens > CHUNK_MAX_TOKENS:
            parts.append(" ".join(buffer).strip())
            overlap = _tail_text([(0, parts[-1])], CHUNK_OVERLAP_TOKENS * 4)
            buffer = [overlap] if overlap else []
            tokens = estimate_tokens(overlap)
        buffer.append(sentence)
        tokens += sentence_tokens
    if buffer:
        parts.append(" ".join(buffer).strip())
    return [part for part in parts if part]


def _chunk_record(
    document_id: str,
    section: str,
    heading_paths: List[List[str]],
    section_index: int,
    chunk_index: int,
    items: List[Tuple[int, str]],
) -> Dict[str, Any]:
    pages = [page for page, _ in items]
    text = "\n\n".join(text for _, text in items).strip()
    return {
        "document_id": document_id,
        "chunk_id": f"{document_id}-s{section_index:02d}-c{chunk_index:03d}",
        "section": section,
        "heading_path": heading_paths[0] if len(heading_paths) == 1 else heading_paths,
        "page_start": min(pages),
        "page_end": max(pages),
        "estimated_tokens": estimate_tokens(text),
        "text": text,
    }


def _blocks(text: str) -> Iterable[str]:
    for block in re.split(r"\n\s*\n", text):
        clean = re.sub(r"\s+", " ", block).strip()
        if clean:
            yield clean


def _heading_info(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    if _looks_like_toc_line(clean) or len(clean) > 160 or len(clean.split()) > 18 or clean.endswith((".", ";", "?")):
        return None
    markdown = re.match(r"^(#{1,6})\s+(.+)$", clean)
    if markdown:
        return {"level": len(markdown.group(1)), "title": markdown.group(2).strip()[:160]}
    numbered = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$", clean)
    if numbered:
        return {"level": min(numbered.group(1).count(".") + 1, 6), "title": clean[:160]}
    if re.match(r"^[A-Z][A-Z0-9 /&-]{5,}$", clean):
        return {"level": 1, "title": clean[:160]}
    return None


def _looks_like_toc_line(text: str) -> bool:
    return bool(re.match(r"^(\d+(?:\.\d+)*\.?\s+)?[^.]{3,120}\.{2,}\s*\d+\s*$", text))


def _update_heading_path(current_path: List[str], level: int, title: str) -> List[str]:
    level = max(1, min(level, 6))
    next_path = current_path[: level - 1]
    next_path.append(title)
    return next_path


def _tail_text(items: List[Tuple[int, str]], limit: int) -> str:
    text = "\n\n".join(value for _, value in items)
    return text[-limit:].lstrip()


def _tail_tokens(items: List[Tuple[int, str]], limit: int) -> str:
    text = "\n\n".join(value for _, value in items)
    words = re.findall(r"\S+", text)
    return " ".join(words[-limit:]).lstrip()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)
