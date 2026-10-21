# Client deployment requirements

## Demonstration workstation

- Windows 10 or Windows 11, 64-bit
- 4 logical CPU cores minimum; 8 recommended
- 8 GB RAM minimum; 16 GB recommended
- 3 GB free disk space plus storage for drawings and generated outputs
- A current Chromium-based browser or Firefox at 1366×768 or larger
- Python 3.11 or 3.12 and the repository virtual environment
- Node.js/npm only when rebuilding the frontend; it is not required to run an
  already built single-server package
- Optional local Tesseract installation when raster supplier OCR is enabled

No cloud account, external AI API, database, or internet connection is required at
runtime. Drawings and outputs remain on the workstation.

## Network and ports

The demonstration defaults to `127.0.0.1:8000`, so it is reachable only from the
local machine. If IT chooses a different host binding, it must provide firewall,
TLS, authentication, authorization, audit retention, and reverse-proxy controls;
those are production deployment concerns outside this PoC.

## Installation

1. Create `.venv` and install `backend/requirements.txt` (and the development file
   for test tooling).
2. In `frontend`, install locked JavaScript dependencies and run `npm run build`.
3. Keep `frontend/dist` with the backend package.
4. Run `start_demo.bat`; it validates prerequisites, starts FastAPI, checks health,
   and opens the production UI.

Inputs are read from uploads. Persistent records are written under
`data/output/drawings` by default. This location needs write permission and should
be included in the client’s backup/retention policy.

## Configuration

Environment variables include `DRAWING_MAX_UPLOAD_BYTES`,
`DRAWING_STORAGE_DIR`, `DRAWING_LEVEL3_ENABLED`, `DRAWING_LEVEL4_ENABLED`,
`DRAWING_OCR_ENABLED`, `DRAWING_OCR_PROVIDER`, and `DRAWING_DEMO_MODE`.
Controlled validation, visual, and relationship policies reside under `config/`.
Changes to supplier mappings or SCC semantics require engineering governance and
regression testing.

## Production hardening before operational use

The PoC is suitable for controlled local demonstration, not unqualified production
acceptance. Production work should add identity/access control, encrypted transport,
malware scanning, centralized logging, retention/deletion policy, dependency/SBOM
management, load testing, signed releases, monitoring, disaster recovery, and a
reviewed ground-truth validation program.

