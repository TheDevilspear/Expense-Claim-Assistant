# Agent Extraction Confidence & Zero Synthetic Fallback Rules

## 1. Zero Synthetic Fallbacks
- **No Dummy Defaults**: Never inject synthetic fallback defaults (e.g. hardcoded amounts, default vendor names, or hash-generated invoice IDs).
- **Explicit Missing Representation**: If a field is not directly extracted from verified text or vision output, set `value = None`, `raw_text = None`, `confidence = 0.0`, and `explanation = "Field missing/unreadable in document"`.

## 2. Honest Confidence Integrity
- **No False High Confidence**: Never report high confidence ($\ge 0.80$) unless the value was directly verified from document text.
- **Downstream Gate Integrity**: Allow $0.0$ confidence scores to trigger downstream verification gates (`CONFIDENCE_GATE`), ensuring unconfirmed fields route to human review (`ESCALATE_TO_HUMAN`).

## 3. Smart & Context-Aware Keyword Extraction
- **Word Boundaries**: Enforce regex word boundaries (`\b`) when matching vendor/brand keywords.
- **Prevent Substring Collisions**: Never perform raw substring checks (`"act" in text`) that collide with common words like `"account"`, `"transaction"`, or `"contact"`.

## 4. Vision API Timeout Margins
- Set API timeouts to $\ge 25\text{s}$ for vision LLM inference calls to prevent premature fall-through.
