# Drawing review corpus

`pdfs/` contains the 16 client-supplied PDFs used for the detector-improvement
cycle. The source files are copied unchanged; `scripts/audit_training_corpus.py`
records SHA-256 hashes and PDF metadata in `data/output/training_audit/`.

This is an unlabelled review corpus, not statistical-model training data.
Detector predictions must not be copied into `tests/vision_ground_truth/`.
Precision, recall, F1, and completeness claims remain unavailable until a human
reviewer independently annotates the visual-object ground truth.

Run the reproducible audit from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\audit_training_corpus.py --debug-overlays
```

The output keeps the layers separate:

- `extraction/`: evidence-preserving Level-1 output;
- `vision/`: Level-3 detector predictions;
- `overlays/`: review images, never ground truth;
- `corpus_audit.json` and `.csv`: corpus manifest and run summary.

