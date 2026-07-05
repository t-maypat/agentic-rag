"""Pure text-chunking logic (no I/O, no network).

Splits documents into overlapping sentence-packed chunks, respecting markdown
section headings. Ported from the original ``services/text_splitter.py`` and kept
free of config/SDK imports so it is trivially unit-testable.
"""

import re
from dataclasses import dataclass

from app.models import DocumentSection


@dataclass(frozen=True)
class ChunkResult:
    text: str
    section: str | None
    chunk_index: int


def _compact(text: str) -> str:
    return " ".join(text.split())


def _split_markdown_sections(text: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    buffer: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if buffer:
                sections.append((current_heading, "\n".join(buffer).strip()))
                buffer = []
            current_heading = stripped.lstrip("#").strip() or None
        else:
            buffer.append(line)

    if buffer:
        sections.append((current_heading, "\n".join(buffer).strip()))

    return [(heading, body) for heading, body in sections if body.strip()]


def _sentence_split(text: str) -> list[str]:
    compact = _compact(text)
    if not compact:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", compact) if s.strip()]


def _pack_sentences(sentences: list[str], max_chars: int, overlap: int) -> list[str]:
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append(" ".join(current).strip())
        if overlap <= 0:
            current = []
            current_len = 0
            return
        carry: list[str] = []
        carry_len = 0
        for sentence in reversed(current):
            sentence_len = len(sentence) + (1 if carry else 0)
            if carry_len + sentence_len > overlap and carry:
                break
            carry.insert(0, sentence)
            carry_len += sentence_len
        current = carry
        current_len = carry_len

    for sentence in sentences:
        sentence_len = len(sentence) + (1 if current else 0)
        if current and current_len + sentence_len > max_chars:
            flush()
        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(" ".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def _split_section_text(text: str, max_chars: int, overlap: int) -> list[str]:
    sentences = _sentence_split(text)
    chunks = _pack_sentences(sentences, max_chars, overlap)
    if chunks:
        return chunks

    compact = _compact(text)
    if not compact:
        return []
    return [compact[i : i + max_chars].strip() for i in range(0, len(compact), max_chars)]


def split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    return _split_section_text(text, max_chars, overlap)


def split_document(
    text: str,
    sections: list[DocumentSection] | None,
    max_chars: int,
    overlap: int,
) -> list[ChunkResult]:
    section_blocks: list[tuple[str | None, str]] = []
    if sections:
        for section in sections:
            if section.text.strip():
                section_blocks.append((section.heading, section.text))
    else:
        section_blocks = _split_markdown_sections(text)

    if not section_blocks and text.strip():
        section_blocks = [(None, text)]

    results: list[ChunkResult] = []
    chunk_index = 0
    for heading, body in section_blocks:
        for chunk in _split_section_text(body, max_chars, overlap):
            results.append(ChunkResult(text=chunk, section=heading, chunk_index=chunk_index))
            chunk_index += 1

    return results
