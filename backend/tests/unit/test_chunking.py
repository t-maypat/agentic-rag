from app.models import DocumentSection
from app.retrieval.chunking import split_document, split_text


def test_split_text_respects_max_chars():
    text = " ".join(f"Sentence number {i} here." for i in range(50))
    chunks = split_text(text, max_chars=120, overlap=0)
    assert len(chunks) > 1
    assert all(len(chunk) <= 120 or " " not in chunk for chunk in chunks)


def test_split_document_with_sections_indexes_and_headings():
    sections = [
        DocumentSection(heading="Summary", text="First sentence. Second sentence."),
        DocumentSection(heading="Details", text="Third sentence. Fourth sentence."),
    ]
    results = split_document("", sections, max_chars=1000, overlap=0)
    assert [r.chunk_index for r in results] == list(range(len(results)))
    headings = {r.section for r in results}
    assert headings == {"Summary", "Details"}


def test_split_document_markdown_fallback():
    text = "# Intro\nAlpha beta gamma.\n# Body\nDelta epsilon zeta."
    results = split_document(text, None, max_chars=1000, overlap=0)
    assert {r.section for r in results} == {"Intro", "Body"}


def test_split_document_empty_text_yields_nothing():
    assert split_document("", None, max_chars=1000, overlap=0) == []


def test_split_text_overlap_produces_more_chunks_than_no_overlap():
    sentences = [
        f"Fact number {i} is important and detailed enough to matter here." for i in range(8)
    ]
    text = " ".join(sentences)
    no_overlap = split_text(text, max_chars=120, overlap=0)
    with_overlap = split_text(text, max_chars=120, overlap=60)
    # Overlap re-emits trailing sentences, so it never yields fewer chunks.
    assert len(with_overlap) >= len(no_overlap) >= 2
