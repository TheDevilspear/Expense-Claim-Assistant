"""
Evidence-based document extraction pipeline.

Stages:
1. document_inspector   — Per-page profiling & routing
2. page_extractor       — Native PDF coordinates + OCR → PageEvidence
3. candidate_extractor  — All money/date/ID/vendor candidates
4. semantic_classifier  — Label → semantic type mapping
5. section_classifier   — Page → document section classification
6. field_selector       — Priority ranking, reconciliation, confidence
7. vision_arbitrator    — Targeted Vision LLM for ambiguous fields
"""
