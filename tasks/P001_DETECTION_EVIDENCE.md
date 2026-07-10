# P001_DETECTION_EVIDENCE

Enrich the `Detection` model with explainability fields: `detection_id` (deterministic hash of page_number + detection_type + span + text — stable across runs on the same document) and `reasons: list[str]` (human-readable evidence, e.g. "matches PAN format", "Verhoeff checksum passed", "near label 'A/c No'"). Thread through all detectors and fusion (fusion must preserve/merge reasons). Update tests. No behavior change to detection itself — this is the substrate for context scoring (P002) and the review plan (P006).
