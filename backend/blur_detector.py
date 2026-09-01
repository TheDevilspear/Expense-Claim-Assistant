"""
Custom Blur & Image Quality Detector for Expense Invoices and Receipts.
Implements a 3-metric ensemble:
1. Laplacian Variance (Bilateral Denoised) - Text edge sharpness
2. 2D FFT High-Frequency Energy Ratio - Frequency domain sharpness
3. Canny Edge Density - Structural edge concentration
Includes automatic text-region cropping and digital vs. photo domain calibration.
"""

import sys
import json
import os
from dataclasses import dataclass, asdict
from typing import Union, List, Optional
import numpy as np
import cv2
from numpy.fft import fft2, fftshift

# Calibrated domain reference configurations
CONFIG = {
    "digital": {
        "threshold": 0.4426,
        "lap_ref": 1720.84,
        "fft_ref": 0.8138,
        "edge_ref": 10.8885,
        "texture_threshold": 5.0,
    },
    "photo": {
        "threshold": 0.3753,
        "lap_ref": 485.85,
        "fft_ref": 0.7107,
        "edge_ref": 13.638,
        "texture_threshold": 5.0,
    },
}

@dataclass
class BlurResult:
    filename: str
    is_blur: bool
    quality_label: str
    ensemble_score: float
    laplacian_var: float
    fft_highfreq_ratio: float
    edge_density: float
    domain: str
    indeterminate: bool = False
    details: Optional[str] = None

    def to_dict(self):
        return asdict(self)


from extraction.pdf_utils import load_file_as_grayscale_numpy


def load_image_as_gray(file_path_or_bytes: Union[str, bytes]) -> np.ndarray:
    """Loads image or first page of PDF as grayscale numpy array."""
    return load_file_as_grayscale_numpy(file_path_or_bytes)



def crop_text_region(gray_img: np.ndarray) -> np.ndarray:
    """
    Isolates text regions using Sobel vertical edge filter, Otsu thresholding,
    and horizontal morphological clustering to filter out blank borders and noise.
    """
    h, w = gray_img.shape
    if h < 50 or w < 50:
        return gray_img

    # Detect vertical transitions characteristic of printed text
    sobel = cv2.Sobel(gray_img, cv2.CV_8U, 1, 0, ksize=3)
    _, thresh = cv2.threshold(sobel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Group characters into text line blocks (35px width x 5px height)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bboxes = []

    for c in contours:
        x, y, wb, hb = cv2.boundingRect(c)
        if 5 <= hb <= 80 and wb >= 15:
            bboxes.append((x, y, x + wb, y + hb))

    if not bboxes:
        return gray_img

    bboxes_arr = np.array(bboxes)
    min_x = max(0, int(bboxes_arr[:, 0].min()) - 15)
    min_y = max(0, int(bboxes_arr[:, 1].min()) - 15)
    max_x = min(w, int(bboxes_arr[:, 2].max()) + 15)
    max_y = min(h, int(bboxes_arr[:, 3].max()) + 15)

    cropped = gray_img[min_y:max_y, min_x:max_x]
    return cropped if cropped.size > 0 else gray_img


def compute_laplacian_var(gray_img: np.ndarray) -> float:
    """Computes Laplacian variance after bilateral denoising."""
    denoised = cv2.bilateralFilter(gray_img, d=5, sigmaColor=50, sigmaSpace=50)
    return float(cv2.Laplacian(denoised, cv2.CV_64F).var())


def compute_fft_ratio(gray_img: np.ndarray) -> float:
    """Computes high-frequency energy ratio using 2D FFT."""
    h, w = gray_img.shape
    if h == 0 or w == 0:
        return 0.0
    f_transform = fft2(gray_img.astype(np.float64))
    f_shift = fftshift(f_transform)
    magnitude = np.abs(f_shift)

    cy, cx = h // 2, w // 2
    r = min(h, w) * 0.1
    y, x = np.ogrid[:h, :w]
    low_freq_mask = ((x - cx) ** 2 + (y - cy) ** 2) <= (r ** 2)

    total_energy = magnitude.sum()
    low_energy = magnitude[low_freq_mask].sum()
    return float((total_energy - low_energy) / (total_energy + 1e-8))


def compute_edge_density(gray_img: np.ndarray) -> float:
    """Computes Canny edge pixel density."""
    edges = cv2.Canny(gray_img, 50, 150)
    return float(edges.sum() / (gray_img.size + 1e-8))


def normalize_metric(raw_val: float, ref_val: float) -> float:
    """Non-linear soft normalization: S = raw / (raw + ref)."""
    return raw_val / (raw_val + ref_val + 1e-8)


def detect_blur(file_path: str, max_dim: int = 1024) -> BlurResult:
    """
    Main entrypoint: Analyzes an image or PDF file and returns a BlurResult.
    """
    filename = os.path.basename(file_path)
    gray = load_image_as_gray(file_path)

    # 1. Domain Detection (Digital screenshot vs. Camera photo)
    is_digital = (gray >= 254).sum() / gray.size > 0.50
    domain = "digital" if is_digital else "photo"
    cfg = CONFIG[domain]

    # 2. Text Region Isolation
    cropped = crop_text_region(gray)

    # 3. Resize to standard max dimension for consistent scale
    h, w = cropped.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        cropped = cv2.resize(cropped, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # 4. Metric Calculations
    lap_var = compute_laplacian_var(cropped)

    # Indeterminate check (blank or textureless page)
    if lap_var < cfg["texture_threshold"]:
        return BlurResult(
            filename=filename,
            is_blur=False,
            quality_label="Clear (Indeterminate/Low Texture)",
            ensemble_score=1.0,
            laplacian_var=round(lap_var, 2),
            fft_highfreq_ratio=0.0,
            edge_density=0.0,
            domain=domain,
            indeterminate=True,
            details="Page has very low texture (possibly blank digital document).",
        )

    fft_ratio = compute_fft_ratio(cropped)
    edge_density = compute_edge_density(cropped)

    # 5. Ensemble Weighted Soft Scoring (Laplacian weight: 2, FFT weight: 1, Edge weight: 1)
    lap_score = normalize_metric(lap_var, cfg["lap_ref"])
    fft_score = normalize_metric(fft_ratio, cfg["fft_ref"])
    edge_score = normalize_metric(edge_density, cfg["edge_ref"])

    ensemble = (2.0 * lap_score + 1.0 * fft_score + 1.0 * edge_score) / 4.0
    threshold = cfg["threshold"]
    is_blur = ensemble < threshold

    if is_blur:
        quality_label = f"Blurry / Low Legibility ({round(ensemble * 100)}%)"
    else:
        quality_label = f"Sharp & Clear ({round(ensemble * 100)}%)"

    return BlurResult(
        filename=filename,
        is_blur=bool(is_blur),
        quality_label=quality_label,
        ensemble_score=round(float(ensemble), 4),
        laplacian_var=round(float(lap_var), 2),
        fft_highfreq_ratio=round(float(fft_ratio), 4),
        edge_density=round(float(edge_density), 4),
        domain=domain,
        indeterminate=False,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python blur_detector.py <image_or_pdf_path>"}))
        sys.exit(1)

    target_path = sys.argv[1]
    try:
        result = detect_blur(target_path)
        print(json.dumps(result.to_dict(), indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e), "filename": os.path.basename(target_path)}))
        sys.exit(1)
