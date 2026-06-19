"""Extract plain text from uploaded files for LLM ingestion."""

from __future__ import annotations

import email as _email
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_CHARS = 8_000  # per-file cap before sending to LLM


def extract_text(filename: str, raw: bytes) -> str:
    """Return plain-text representation of a file, capped at _MAX_CHARS."""
    ext = Path(filename).suffix.lower()
    try:
        if ext in (".csv", ".tsv", ".txt", ".md", ".ics"):
            text = raw.decode("utf-8-sig", errors="replace")
        elif ext == ".eml":
            text = _extract_eml(raw)
        elif ext == ".pdf":
            text = _extract_pdf(raw)
        else:
            # Generic fallback — try UTF-8, skip if binary
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                logger.warning("Skipping binary file: %s", filename)
                return ""
    except Exception as exc:
        logger.warning("Failed to extract text from %s: %s", filename, exc)
        return ""

    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS] + "\n[...truncated...]"
    return text


def _extract_eml(raw: bytes) -> str:
    msg = _email.message_from_bytes(raw)
    parts: list[str] = []

    for header in ("From", "To", "Cc", "Date", "Subject"):
        val = msg.get(header, "")
        if val:
            parts.append(f"{header}: {val}")

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode("utf-8", errors="replace"))
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            parts.append(payload.decode("utf-8", errors="replace"))

    return "\n".join(parts)


def _extract_pdf(raw: bytes) -> str:
    try:
        import io
        import pypdf  # type: ignore[import]

        reader = pypdf.PdfReader(io.BytesIO(raw))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n".join(pages)
    except ImportError:
        logger.warning("pypdf not installed; cannot extract PDF text")
        return "[PDF extraction unavailable — install pypdf]"
