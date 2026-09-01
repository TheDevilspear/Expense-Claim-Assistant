"""
Stage 2: Per-Page Evidence Extractor.

Converts each page into a standardized PageEvidence object containing
tokens with normalized bounding boxes and reconstructed lines.

The critical abstraction: after this stage, downstream pipeline stages
never need to know whether the source was a native PDF or an OCR scan.
"""

from typing import List, Optional
from models.extraction_schema import (
    Token,
    Line,
    PageProfile,
    PageEvidence,
    PageRoute,
    ExtractionMethod,
)


def extract_page_evidence(file_path: str, page_profile: PageProfile) -> PageEvidence:
    """
    Extracts structured evidence from a single page.

    For NATIVE_PDF / NATIVE_PDF_DEGRADED: uses PyMuPDF word coordinates.
    For OCR_REQUIRED / IMAGE_OCR: renders page and runs OCR.
    For EMPTY_PAGE: returns empty evidence.
    """
    if page_profile.route in (PageRoute.NATIVE_PDF, PageRoute.NATIVE_PDF_DEGRADED):
        return _extract_native_pdf_page(file_path, page_profile.page_number)

    if page_profile.route in (PageRoute.OCR_REQUIRED, PageRoute.IMAGE_OCR):
        return _extract_ocr_page(file_path, page_profile)

    # EMPTY_PAGE
    return PageEvidence(
        page_number=page_profile.page_number,
        tokens=[],
        lines=[],
        raw_text="",
        extraction_method=ExtractionMethod.NATIVE_PDF,
    )


def _extract_native_pdf_page(file_path: str, page_number: int) -> PageEvidence:
    """Extracts tokens with normalized coordinates from a native PDF page."""
    try:
        import fitz
    except ImportError:
        return PageEvidence(
            page_number=page_number, tokens=[], lines=[],
            raw_text="", extraction_method=ExtractionMethod.NATIVE_PDF,
        )

    doc = fitz.open(file_path)
    page = doc[page_number]
    rect = page.rect
    width = rect.width or 1.0
    height = rect.height or 1.0

    # Get plain text for raw_text field
    raw_text = page.get_text("text") or ""

    # Get positioned words: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
    words = page.get_text("words") or []

    tokens = []
    for w in words:
        text = w[4].strip()
        if not text:
            continue
        tokens.append(Token(
            text=text,
            x0=w[0] / width,
            y0=w[1] / height,
            x1=w[2] / width,
            y1=w[3] / height,
        ))

    doc.close()

    # Cluster tokens into lines
    lines = cluster_tokens_into_lines(tokens)

    return PageEvidence(
        page_number=page_number,
        tokens=tokens,
        lines=lines,
        raw_text=raw_text.strip(),
        extraction_method=ExtractionMethod.NATIVE_PDF,
    )


def _extract_ocr_page(file_path: str, page_profile: PageProfile) -> PageEvidence:
    """
    Renders a page as an image and runs OCR to extract tokens.
    Falls back to empty evidence if OCR dependencies aren't available.
    """
    img_bytes, img_width, img_height = _render_page_to_image(file_path, page_profile)

    if img_bytes is None:
        return PageEvidence(
            page_number=page_profile.page_number, tokens=[], lines=[],
            raw_text="", extraction_method=ExtractionMethod.OCR,
        )

    tokens = _run_ocr(img_bytes, img_width, img_height)
    lines = cluster_tokens_into_lines(tokens)
    raw_text = " ".join(line.full_text for line in lines)

    return PageEvidence(
        page_number=page_profile.page_number,
        tokens=tokens,
        lines=lines,
        raw_text=raw_text,
        extraction_method=ExtractionMethod.OCR,
    )


_EASYOCR_READER = None


def _get_easyocr_reader():
    """Lazy-load and cache the EasyOCR reader singleton for fast inferences."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        except Exception:
            _EASYOCR_READER = False
    return _EASYOCR_READER if _EASYOCR_READER is not False else None


from extraction.pdf_utils import render_page_to_bytes


def _render_page_to_image(file_path: str, page_profile: PageProfile):
    """Renders a PDF page or loads an image file as bytes. Returns (bytes, width, height)."""
    return render_page_to_bytes(file_path, page_number=page_profile.page_number, dpi=200, img_format="png")



def _run_ocr(img_bytes: bytes, img_width: int, img_height: int) -> List[Token]:
    """
    Runs local OCR on image bytes and returns normalized spatial tokens.
    Uses EasyOCR first with bounding box normalization, falling back to pytesseract.
    """
    width = img_width or 1
    height = img_height or 1

    # 1. Try EasyOCR (Neural Network OCR)
    reader = _get_easyocr_reader()
    if reader is not None:
        try:
            results = reader.readtext(img_bytes)
            # results format: [(bbox, text, confidence), ...]
            # bbox: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
            tokens = []
            for bbox, text, prob in results:
                clean_text = text.strip()
                if not clean_text or prob < 0.20:
                    continue

                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                x0 = min(xs) / width
                x1 = max(xs) / width
                y0 = min(ys) / height
                y1 = max(ys) / height

                # Split multi-word bounding boxes into individual words for token-level precision
                words = clean_text.split()
                if len(words) > 1:
                    w_step = (x1 - x0) / len(words)
                    for idx, word in enumerate(words):
                        tokens.append(Token(
                            text=word,
                            x0=x0 + idx * w_step,
                            y0=y0,
                            x1=x0 + (idx + 1) * w_step,
                            y1=y1,
                        ))
                else:
                    tokens.append(Token(
                        text=clean_text,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                    ))
            if tokens:
                return tokens
        except Exception:
            pass

    # 2. Fallback to pytesseract if installed
    try:
        import pytesseract
        from PIL import Image
        import io

        image = Image.open(io.BytesIO(img_bytes))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        tokens = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text or int(data["conf"][i]) < 30:
                continue
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            tokens.append(Token(
                text=text,
                x0=x / width,
                y0=y / height,
                x1=(x + w) / width,
                y1=(y + h) / height,
            ))
        return tokens
    except Exception:
        pass

    return []


def cluster_tokens_into_lines(tokens: List[Token], tolerance: float = 0.008) -> List[Line]:
    """
    Groups tokens whose vertical center is within `tolerance` (normalized)
    of each other into the same logical line. Then sorts each line left-to-right.

    tolerance=0.008 ≈ 0.8% of page height ≈ 6–7 points on A4 at 842pt height.
    """
    if not tokens:
        return []

    # Sort by vertical center
    sorted_tokens = sorted(tokens, key=lambda t: t.y_center)

    lines: List[Line] = []
    current_tokens = [sorted_tokens[0]]
    current_y = sorted_tokens[0].y_center

    for token in sorted_tokens[1:]:
        if abs(token.y_center - current_y) <= tolerance:
            current_tokens.append(token)
        else:
            # Finalize current line: sort left-to-right
            current_tokens.sort(key=lambda t: t.x0)
            full_text = " ".join(t.text for t in current_tokens)
            lines.append(Line(tokens=list(current_tokens), full_text=full_text, y_center=current_y))
            current_tokens = [token]
            current_y = token.y_center

    # Don't forget the last line
    if current_tokens:
        current_tokens.sort(key=lambda t: t.x0)
        full_text = " ".join(t.text for t in current_tokens)
        lines.append(Line(tokens=list(current_tokens), full_text=full_text, y_center=current_y))

    return lines
