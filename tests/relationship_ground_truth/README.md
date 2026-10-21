# Level 4 relationship ground truth

Level 4 accuracy is calculated only from JSON files in this directory whose
`review_status` is `MANUALLY_REVIEWED`. The evaluator never treats engine output as
ground truth.

Create one file per PDF using the PDF stem as the filename. Each expectation must
name a relationship rule and expected status. If a rule emits more than one finding,
also provide the stable `finding_id` so the expectation is unambiguous. See
`schema.json` for the machine-readable contract.
