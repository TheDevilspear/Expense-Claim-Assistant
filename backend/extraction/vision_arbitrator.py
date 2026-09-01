"""
Stage 7: Vision LLM Arbitrator with Resilient Fallback.

Invoked ONLY when local extraction produces ambiguous or missing results.
Sends targeted, per-field prompts to the Vision LLM instead of asking it
to "extract everything" from the entire document.

Resilience Guarantee:
If the OpenRouter API key is invalid, missing, rate-limited, timed out,
or unreachable, this module logs the incident and returns None cleanly,
allowing the deterministic rule/heuristic pipeline to continue without failure.
"""

import sys
import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import List, Optional
from pathlib import Path

import config
from models.extraction_schema import Candidate, FieldType
from extraction.pdf_utils import render_page_to_data_uri

logger = logging.getLogger(__name__)


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
    Returns dict with {"value": ..., "reasoning": "..."} or None on any API/network failure.
    """
    api_key = config.get_api_key()
    if not api_key:
        logger.debug("OpenRouter API key not configured; skipping vision arbitration.")
        return None

    model = config.get_vision_model()
    base_url = config.get_base_url()
    timeout = config.get_timeout()

    # Normalize endpoint URL
    clean_base = base_url.strip().rstrip("/")
    if clean_base.endswith("/chat/completions"):
        endpoint_url = clean_base
    elif clean_base.endswith("/v1"):
        endpoint_url = f"{clean_base}/chat/completions"
    elif clean_base.endswith("/api"):
        endpoint_url = f"{clean_base}/v1/chat/completions"
    elif "openrouter.ai" in clean_base and "/v1" not in clean_base:
        endpoint_url = f"{clean_base}/api/v1/chat/completions"
    else:
        endpoint_url = f"{clean_base}/chat/completions"

    # Render the specific page as a data URI
    image_data_uri = render_page_to_data_uri(file_path, page_number)
    if not image_data_uri:
        logger.warning("Could not render page %d of %s to data URI for vision arbitration.", page_number, file_path)
        return None

    # Build targeted prompt
    prompt = _build_targeted_prompt(field_name, candidates)

    candidate_models = [model]
    # Fast fallback vision models on OpenRouter in case primary is unavailable/404
    fallback_pool = [
        "google/gemini-2.0-flash-001",
        "openrouter/free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
    ]
    for fb in fallback_pool:
        if fb not in candidate_models:
            candidate_models.append(fb)

    import time
    start_time = time.time()
    max_budget_seconds = 4.0  # Max total time allowed for vision arbitration per field
    per_model_timeout = min(timeout, 2.5)

    import socket
    socket.setdefaulttimeout(per_model_timeout)

    for current_model in candidate_models[:3]:  # Try at most 3 models within budget
        elapsed = time.time() - start_time
        if elapsed >= max_budget_seconds:
            logger.info("Vision arbitration budget exceeded (%.1fs); falling back to local extraction.", elapsed)
            break

        remaining_timeout = max(1.0, min(per_model_timeout, max_budget_seconds - elapsed))

        payload = {
            "model": current_model,
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
            req = urllib.request.Request(
                endpoint_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://expense-claim-assistant.onrender.com",
                    "X-Title": "Expense Claim Assistant",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=remaining_timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                data = json.loads(resp_body)

                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"]
                    json_match = re.search(r"\{.*\}", content, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                        logger.info("Vision arbitration succeeded (%s) for field '%s': %s", current_model, field_name, parsed.get("value"))
                        return parsed
                elif "error" in data:
                    logger.warning("OpenRouter API error response (%s): %s", current_model, data["error"])

        except urllib.error.HTTPError as http_err:
            err_body = ""
            try:
                err_body = http_err.read().decode("utf-8")
            except Exception:
                pass
            logger.warning(
                "OpenRouter HTTP %d error for model '%s' on %s (field '%s'): %s | Response: %s",
                http_err.code, current_model, endpoint_url, field_name, http_err.reason, err_body
            )
            # If 404 or 429, loop to next fallback model
            continue
        except (urllib.error.URLError, socket.timeout, TimeoutError) as net_err:
            logger.warning("OpenRouter timeout/connection error for model '%s': %s", current_model, net_err)
            continue
        except Exception as err:
            logger.warning("Vision arbitration unexpected exception: %s", err)
            break

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
