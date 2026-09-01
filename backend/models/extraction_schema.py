"""
Intermediate data models for the evidence-based extraction pipeline.
These are internal-only — the API boundary schemas (ExtractedInvoice, MakerOutput)
in maker_schema.py remain unchanged.

All models are plain dataclasses for zero-dependency, low-overhead internal use.
Coordinates are normalized to 0.0–1.0 so layout logic is resolution-independent.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExtractionMethod(str, Enum):
    NATIVE_PDF = "native_pdf"
    OCR = "ocr"
    VISION_LLM = "vision_llm"


class PageRoute(str, Enum):
    NATIVE_PDF = "native_pdf"
    NATIVE_PDF_DEGRADED = "native_pdf_degraded"
    OCR_REQUIRED = "ocr_required"
    IMAGE_OCR = "image_ocr"
    EMPTY_PAGE = "empty_page"


class FieldType(str, Enum):
    MONEY = "money"
    DATE = "date"
    IDENTIFIER = "identifier"
    VENDOR = "vendor"
    VALIDITY = "validity"


class MoneySemanticType(str, Enum):
    TOTAL_AMOUNT_PAYABLE = "TOTAL_AMOUNT_PAYABLE"
    CURRENT_BILL_AMOUNT = "CURRENT_BILL_AMOUNT"
    PAID_AMOUNT = "PAID_AMOUNT"
    RECHARGE_AMOUNT = "RECHARGE_AMOUNT"
    SERVICE_COMPONENT = "SERVICE_COMPONENT"
    TAX = "TAX"
    PREVIOUS_BALANCE = "PREVIOUS_BALANCE"
    LATE_FEE = "LATE_FEE"
    DISCOUNT = "DISCOUNT"
    OTHER = "OTHER"


class DateSemanticType(str, Enum):
    INVOICE_DATE = "INVOICE_DATE"
    BILL_DATE = "BILL_DATE"
    PAYMENT_DATE = "PAYMENT_DATE"
    DUE_DATE = "DUE_DATE"
    BILLING_PERIOD_START = "BILLING_PERIOD_START"
    BILLING_PERIOD_END = "BILLING_PERIOD_END"
    TRANSACTION_TIMESTAMP = "TRANSACTION_TIMESTAMP"
    ACTIVATION_DATE = "ACTIVATION_DATE"
    OTHER_DATE = "OTHER_DATE"


class IdentifierSemanticType(str, Enum):
    ACCOUNT_NUMBER = "ACCOUNT_NUMBER"
    INVOICE_NUMBER = "INVOICE_NUMBER"
    TRANSACTION_ID = "TRANSACTION_ID"
    STATEMENT_NUMBER = "STATEMENT_NUMBER"
    REFERENCE_NUMBER = "REFERENCE_NUMBER"
    OTHER_ID = "OTHER_ID"


class SectionType(str, Enum):
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT"
    POSTPAID_BILL = "POSTPAID_BILL"
    PREPAID_RECHARGE = "PREPAID_RECHARGE"
    BROADBAND_BILL = "BROADBAND_BILL"
    COMBINED_BILL = "COMBINED_BILL"
    EXPLANATORY = "EXPLANATORY"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# Spatial / Token models (coordinates normalized to 0.0–1.0)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Token:
    """Single word with normalized bounding box."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: Optional[float] = None
    is_bold: bool = False

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2.0


@dataclass(slots=True)
class Line:
    """Group of tokens on the same horizontal band, sorted left-to-right."""
    tokens: List[Token]
    full_text: str
    y_center: float


# ---------------------------------------------------------------------------
# Page-level models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PageProfile:
    """Per-page metadata used for routing decisions."""
    page_number: int
    native_text_length: int
    word_count: int
    has_images: bool
    route: PageRoute


@dataclass(slots=True)
class PageEvidence:
    """
    Standardized extraction output for one page.
    Same shape regardless of whether source was native PDF, OCR, or Vision LLM.
    """
    page_number: int
    tokens: List[Token]
    lines: List[Line]
    raw_text: str
    extraction_method: ExtractionMethod


# ---------------------------------------------------------------------------
# Document-level models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DocumentProfile:
    """Whole-document metadata for routing."""
    file_type: str  # "pdf" or "image"
    page_count: int
    pages: List[PageProfile]


@dataclass(slots=True)
class DocumentSection:
    """A classified group of consecutive pages."""
    pages: List[int]
    section_type: SectionType


# ---------------------------------------------------------------------------
# Candidate model
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """
    A single extracted value with its spatial context and label.
    Created during candidate extraction, classified during semantic classification,
    scored during field selection.
    """
    field_type: FieldType
    value: object  # float for MONEY, str for DATE/IDENTIFIER/VENDOR
    raw_text: str
    label: str
    page: int
    semantic_type: Optional[object] = None  # MoneySemanticType / DateSemanticType / etc.
    confidence: float = 0.0
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    evidence_sources: List[str] = field(default_factory=list)
