# Vision ground truth

This directory is reserved for independently and manually reviewed Level-3 object annotations. Detector output must never be copied here as ground truth.

One JSON file may be supplied per source PDF using the PDF stem as the file name. Each object records:

- `page_number`
- `object_type`
- `bounding_box` in original PDF coordinates
- optional `text`
- `reviewer_comment`

No supplied client sample currently has a complete manually reviewed visual annotation set. Consequently `scripts/evaluate_level3.py` reports object metrics as `null` for ungrounded classes instead of reporting an unsupported score.
