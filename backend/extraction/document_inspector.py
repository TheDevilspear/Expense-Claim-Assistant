"""
Stage 1: Document Inspector.

Inspects an uploaded file and produces a DocumentProfile with per-page
metadata and routing decisions. Does NOT extract content — only profiles.

Typical cost: ~2ms per page.
"""

import os
from typing import Optional
from models.extraction_schema import (
    DocumentProfile,
    PageProfile,
    PageRoute,
)


def inspect(file_path: str) -> DocumentProfile:
    """
    Profiles a file and returns per-page routing metadata.

    For PDFs: inspects each page for native text availability and images.
    For images: returns a single-page profile routed to OCR.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"):
        return DocumentProfile(
            file_type="image",
            page_count=1,
            pages=[PageProfile(
                page_number=0,
                native_text_length=0,
                word_count=0,
                has_images=True,
                route=PageRoute.IMAGE_OCR,
            )],
        )

    if ext != ".pdf":
        return DocumentProfile(
            file_type=ext.lstrip("."),
            page_count=1,
            pages=[PageProfile(
                page_number=0,
                native_text_length=0,
                word_count=0,
                has_images=False,
                route=PageRoute.EMPTY_PAGE,
            )],
        )

    # PDF inspection via PyMuPDF
    return _inspect_pdf(file_path)


def _inspect_pdf(file_path: str) -> DocumentProfile:
    """Inspects a PDF page-by-page using PyMuPDF."""
    try:
        import fitz
    except ImportError:
        # If fitz is unavailable, return a minimal profile
        return DocumentProfile(
            file_type="pdf",
            page_count=1,
            pages=[PageProfile(
                page_number=0,
                native_text_length=0,
                word_count=0,
                has_images=True,
                route=PageRoute.OCR_REQUIRED,
            )],
        )

    doc = fitz.open(file_path)
    page_profiles = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Get native text and word count
        raw_text = page.get_text("text") or ""
        text_length = len(raw_text.strip())
        words = page.get_text("words") or []
        word_count = len(words)

        # Check for embedded images
        images = page.get_images(full=True)
        has_images = len(images) > 0

        # Routing decision
        route = _decide_route(text_length, word_count, has_images)

        page_profiles.append(PageProfile(
            page_number=page_num,
            native_text_length=text_length,
            word_count=word_count,
            has_images=has_images,
            route=route,
        ))

    doc.close()

    return DocumentProfile(
        file_type="pdf",
        page_count=len(page_profiles),
        pages=page_profiles,
    )


def _decide_route(text_length: int, word_count: int, has_images: bool) -> PageRoute:
    """Determines the extraction route for a single page."""
    if text_length > 50 and word_count > 10:
        return PageRoute.NATIVE_PDF
    if text_length > 50 and word_count <= 10:
        # Text exists but layout is suspect — rely heavily on coordinates
        return PageRoute.NATIVE_PDF_DEGRADED
    if text_length <= 50 and has_images:
        return PageRoute.OCR_REQUIRED
    if text_length <= 50 and not has_images:
        return PageRoute.EMPTY_PAGE
    return PageRoute.OCR_REQUIRED
