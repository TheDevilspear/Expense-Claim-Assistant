from __future__ import annotations

import os
import base64
from pathlib import Path
from typing import Optional, Tuple, Union, Any

try:
    import numpy as np
except ImportError:
    np = None


try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import cv2
except ImportError:
    cv2 = None



def render_pdf_page_pixmap(file_path: str, page_number: int = 0, dpi: int = 150):
    """Renders a specific page of a PDF as a fitz.Pixmap."""
    if fitz is None or not os.path.exists(file_path):
        return None
    try:
        doc = fitz.open(file_path)
        if page_number >= len(doc):
            doc.close()
            return None
        page = doc[page_number]
        pix = page.get_pixmap(dpi=dpi)
        doc.close()
        return pix
    except Exception:
        return None


def render_page_to_bytes(
    file_path: str,
    page_number: int = 0,
    dpi: int = 200,
    img_format: str = "png",
) -> Tuple[Optional[bytes], int, int]:
    """
    Renders a PDF page or loads an image file as raw bytes with width and height.
    Returns (bytes, width, height).
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        if fitz is None:
            return None, 0, 0
        try:
            doc = fitz.open(file_path)
            if page_number >= len(doc):
                doc.close()
                return None, 0, 0
            page = doc[page_number]
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes(img_format)
            w, h = pix.width, pix.height
            doc.close()
            return img_bytes, w, h
        except Exception:
            return None, 0, 0
    else:
        # Standard image file
        if not os.path.exists(file_path):
            return None, 0, 0
        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()
            # Determine dimensions
            if cv2 is not None:
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    h, w = img.shape[:2]
                    return img_bytes, w, h
            return img_bytes, 0, 0
        except Exception:
            return None, 0, 0


def render_page_to_data_uri(
    file_path: str,
    page_number: int = 0,
    dpi: int = 100,
) -> Optional[str]:
    """
    Renders a PDF page or image file as a compressed base64 data URI suitable for Vision APIs.
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        if fitz is None:
            return None
        try:
            doc = fitz.open(file_path)
            if page_number >= len(doc):
                doc.close()
                return None
            pix = doc[page_number].get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("jpeg")
            doc.close()
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
        except Exception:
            return None

    # Image file
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime = mime_map.get(ext, "image/jpeg")
    try:
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def load_file_as_grayscale_numpy(file_path_or_bytes: Union[str, bytes]) -> np.ndarray:
    """
    Loads an image or the first page of a PDF as a grayscale 2D numpy array.
    """
    if cv2 is None:
        raise ImportError("OpenCV (cv2) is required for image array operations.")

    if isinstance(file_path_or_bytes, bytes):
        nparr = np.frombuffer(file_path_or_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image bytes.")
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    file_path = str(file_path_or_bytes)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Handle PDF files
    if file_path.lower().endswith(".pdf"):
        if fitz is not None:
            doc = fitz.open(file_path)
            if len(doc) == 0:
                doc.close()
                raise ValueError("PDF document is empty.")
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            doc.close()
            if pix.n == 4:
                return cv2.cvtColor(img_data, cv2.COLOR_RGBA2GRAY)
            elif pix.n == 3:
                return cv2.cvtColor(img_data, cv2.COLOR_RGB2GRAY)
            return img_data

    # Standard image format
    img = cv2.imread(file_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image file: {file_path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
