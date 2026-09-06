# Quality, provenance and licensing

## Evidence hierarchy

Keep extraction facts distinguishable from inference:

1. explicit source statement/table/diagram
2. deterministic derivation from explicit source structure (e.g. fixed-ID mask)
3. contextual inference

Only 1 and safe deterministic 2 should normally become structured fields. Put contextual inference in notes or report it outside the bundle unless the user explicitly wants hypothesis material.

## Provenance

Every useful object should retain `source_location` when available. Exact pages are preferred, but section/table-only provenance is valid. Never invent provenance to make a bundle look complete.

## Private/licensed material

- Source material may be analyzed when supplied by the user.
- Do not reproduce or redistribute whole documents.
- Do not embed source PDFs or large verbatim excerpts in the Skill or bundle.
- Default uncertain redistribution status to `private`.
- `licensed` is metadata; licensed files stay in the private managed source area.

## Quality report

When useful, accompany the bundle with a short summary:

- extracted object counts
- high-confidence exact facts
- incomplete/ambiguous fields
- any source contradictions
- any V1 contract limitation encountered
- suggested validation/search terms after import
