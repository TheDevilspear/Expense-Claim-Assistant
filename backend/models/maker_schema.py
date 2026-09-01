"""
Schemas for the Maker Agent.
Works seamlessly with Pydantic v2 if installed, with pure-Python fallback.
Defines:
1. FieldExtraction: A single extracted field with its dedicated confidence score.
2. ExtractedInvoice: All structured fields extracted from the invoice document.
3. CleanedClaim: Cleaned/standardized user-submitted claim details.
4. MakerOutput: The immutable handoff packet passed from Maker to Checker Agent.
"""

from typing import Optional, Literal, Any, Dict
import json

try:
    from pydantic import BaseModel, Field

    class FieldExtraction(BaseModel):
        value: Optional[Any] = Field(None, description="Standardized typed value")
        raw_text: Optional[str] = Field(None, description="Verbatim text visible on receipt")
        confidence: float = Field(
            ..., ge=0.0, le=1.0, description="Confidence score (1.0 = explicit, 0.0 = absent)"
        )
        explanation: Optional[str] = Field(None, description="Rationale for value and confidence")

    class ExtractedInvoice(BaseModel):
        is_relevant_invoice: bool
        detected_document_type: str
        vendor_name: FieldExtraction
        invoice_or_account_number: FieldExtraction
        bill_date: FieldExtraction
        billing_start_date: FieldExtraction
        billing_end_date: FieldExtraction
        validity_days: FieldExtraction
        total_amount_inr: FieldExtraction
        bill_type: FieldExtraction
        international_roaming_charges: Optional[FieldExtraction] = None
        is_blurry_or_unreadable: bool = False

    class CleanedClaim(BaseModel):
        claimed_amount_inr: float
        claimed_category: str
        claimed_start_date: str
        claimed_end_date: str
        claimed_validity_days: int

    NormalizedClaim = CleanedClaim

    class MakerOutput(BaseModel):
        claim_id: str
        invoice_metadata: Dict[str, Any] = Field(default_factory=dict)
        extracted_invoice: ExtractedInvoice
        cleaned_claim: CleanedClaim
        maker_summary: str
        timestamp: str

        @property
        def normalized_claim(self) -> CleanedClaim:
            return self.cleaned_claim

except ImportError:
    from dataclasses import dataclass, asdict, field

    @dataclass
    class FieldExtraction:
        confidence: float
        value: Optional[Any] = None
        raw_text: Optional[str] = None
        explanation: Optional[str] = None

    @dataclass
    class ExtractedInvoice:
        is_relevant_invoice: bool
        detected_document_type: str
        vendor_name: FieldExtraction
        invoice_or_account_number: FieldExtraction
        bill_date: FieldExtraction
        billing_start_date: FieldExtraction
        billing_end_date: FieldExtraction
        validity_days: FieldExtraction
        total_amount_inr: FieldExtraction
        bill_type: FieldExtraction
        international_roaming_charges: Optional[FieldExtraction] = None
        is_blurry_or_unreadable: bool = False

    @dataclass
    class CleanedClaim:
        claimed_amount_inr: float
        claimed_category: str
        claimed_start_date: str
        claimed_end_date: str
        claimed_validity_days: int

    NormalizedClaim = CleanedClaim

    @dataclass
    class MakerOutput:
        claim_id: str
        extracted_invoice: ExtractedInvoice
        cleaned_claim: CleanedClaim
        maker_summary: str
        timestamp: str
        invoice_metadata: Dict[str, Any] = field(default_factory=dict)

        @property
        def normalized_claim(self) -> CleanedClaim:
            return self.cleaned_claim

        def model_dump(self) -> Dict[str, Any]:
            return asdict(self)

        def model_dump_json(self, indent: int = 2) -> str:
            return json.dumps(asdict(self), indent=indent)

        @classmethod
        def model_validate_json(cls, json_str: str) -> "MakerOutput":
            d = json.loads(json_str)
            return cls.model_validate(d)

        @classmethod
        def model_validate(cls, d: Dict[str, Any]) -> "MakerOutput":
            inv = d["extracted_invoice"]
            ir_charges = None
            if inv.get("international_roaming_charges") and isinstance(inv["international_roaming_charges"], dict):
                ir_charges = FieldExtraction(**inv["international_roaming_charges"])
            extracted = ExtractedInvoice(
                is_relevant_invoice=inv["is_relevant_invoice"],
                detected_document_type=inv["detected_document_type"],
                vendor_name=FieldExtraction(**inv["vendor_name"]),
                invoice_or_account_number=FieldExtraction(**inv["invoice_or_account_number"]),
                bill_date=FieldExtraction(**inv["bill_date"]),
                billing_start_date=FieldExtraction(**inv["billing_start_date"]),
                billing_end_date=FieldExtraction(**inv["billing_end_date"]),
                validity_days=FieldExtraction(**inv["validity_days"]),
                total_amount_inr=FieldExtraction(**inv["total_amount_inr"]),
                bill_type=FieldExtraction(**inv["bill_type"]),
                international_roaming_charges=ir_charges,
                is_blurry_or_unreadable=inv.get("is_blurry_or_unreadable", False),
            )
            norm = CleanedClaim(**d.get("cleaned_claim", d.get("normalized_claim", {})))
            return cls(
                claim_id=d["claim_id"],
                invoice_metadata=d.get("invoice_metadata", {}),
                extracted_invoice=extracted,
                cleaned_claim=norm,
                maker_summary=d["maker_summary"],
                timestamp=d["timestamp"],
            )

