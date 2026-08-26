"""
Stage 7: Vision LLM Arbitrator.

Invoked ONLY when local extraction produces ambiguous or missing results.
Sends targeted, per-field prompts to the Vision LLM instead of asking it
to "extract everything" from the entire document.

Typical usage: 0 calls for clean digital PDFs, 1-2 calls for ambiguous fields.
"""

import os
import re
import json
import base64
import urllib.request
import urllib.error
from typing import List, Optional
from pathlib import Path
from models.extraction_schema import Candidate, FieldType


def _load_env():
    """Load .env file for API keys."""
    root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if root_env.exists():
        for line in root_env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


def needs_vision_arbitration(candidates: List[Candidate], field_type: FieldType) -> bool:
    """
    Determines if Vision LLM arbitration is needed for a specific field.
    Returns True only when local extraction is insufficient.
    """
    field_candidates = [c for c in candidates if c.field_type == field_type]

    # Case 1: No candidates found at all
    if not field_candidates:
        return True

    # Case 2: Multiple conflicting values with similar confidence
    if len(field_candidates) > 1:
        values = set()
        for c in field_candidates:
            values.add(c.value)
        if len(values) > 1:
            # Check if all have low confidence
            max_conf = max(c.confidence for c in field_candidates)
            if max_conf < 0.70:
                return True

    # Case 3: Single candidate but very low confidence
    if len(field_candidates) == 1 and field_candidates[0].confidence < 0.40:
        return True

    return False


def arbitrate(
    field_name: str,
    candidates: List[Candidate],
    file_path: str,
    page_number: int = 0,
) -> Optional[dict]:
    """
    Sends a targeted Vision LLM prompt to resolve ambiguity for a specific field.

    Returns dict with {"value": ..., "reasoning": "..."} or None on failure.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    model = os.environ.get("VISION_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

    # Render the specific page as an image
    image_data_uri = _render_page_to_data_uri(file_path, page_number)
    if not image_data_uri:
        return None

    # Build targeted prompt
    prompt = _build_targeted_prompt(field_name, candidates)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise document field extractor for telecom invoices. "
                    "Answer ONLY the specific question asked. Return valid JSON."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    try:
        import socket
        socket.setdefaulttimeout(8.0)
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Expense Claim Assistant",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
            elif "error" in data:
                print(f"[!] OpenRouter API Error: {data['error']}", file=sys.stderr)
    except Exception as err:
        import sys
        print(f"[!] Vision arbitration failed for {field_name}: {err}", file=sys.stderr)

    return None


def _build_targeted_prompt(field_name: str, candidates: List[Candidate]) -> str:
    """
    Builds a focused prompt that asks the Vision LLM to identify or
    arbitrate between specific candidates — NOT extract everything.
    """
    prompt = f"On this telecom invoice page, identify the correct {field_name}.\n\n"

    field_candidates = [c for c in candidates if c.field_type == FieldType.MONEY]
    if not field_candidates:
        field_candidates = candidates

    if field_candidates:
        prompt += "We found these candidates:\n"
        for i, c in enumerate(field_candidates[:6]):  # Max 6 candidates
            label_info = f" (near label: '{c.label}')" if c.label else ""
            prompt += f"  {chr(65 + i)}: {c.raw_text}{label_info}\n"
        prompt += (
            f"\nWhich candidate is the actual {field_name}? "
            'Return JSON: {"selected": "A"|"B"|..., "value": <extracted value>, "reasoning": "..."}\n'
        )
    else:
        prompt += (
            f"Extract the {field_name} value. "
            'Return JSON: {"value": <extracted value>, "reasoning": "..."}\n'
        )

    return prompt


def _render_page_to_data_uri(file_path: str, page_number: int = 0) -> Optional[str]:
    """Renders a specific page as a compressed base64 data URI for fast Vision API calls."""
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(file_path)
            if page_number < len(doc):
                # 100 DPI is optimal for readability while keeping payload < 100 KB
                pix = doc[page_number].get_pixmap(dpi=100)
                img_bytes = pix.tobytes("jpeg")
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                doc.close()
                return f"data:image/jpeg;base64,{b64}"
            doc.close()
        except Exception:
            pass
        return None

    # Direct image file
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime = mime_map.get(ext.lstrip("."), "image/jpeg")
    try:
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None
