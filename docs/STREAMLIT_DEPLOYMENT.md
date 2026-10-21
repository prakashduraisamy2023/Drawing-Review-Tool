# Streamlit multi-device deployment

The Streamlit entry point reuses the existing Level 1–4 Python engines directly.
It does not replace or modify the React/FastAPI application.

## Local network

Run `start_streamlit.bat` and keep its terminal window open. On the host computer,
open `http://127.0.0.1:8501`. On another phone, tablet, or computer connected to the
same trusted network, open the **Network URL** printed by Streamlit.

If another device cannot connect, allow TCP port 8501 through the Windows firewall
for private networks. Do not expose the development server directly to the public
internet. Use a managed deployment with authentication for internet access.

## Command-line start

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

## Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud and connect the GitHub account that can
   access `prakashduraisamy2023/Drawing-Review-Tool`.
2. Select **Create app** and choose that repository and the `main` branch.
3. Set the entry point to `streamlit_app.py`.
4. Choose a supported Python version compatible with the project (Python 3.11 or
   3.12 is recommended).
5. Deploy and use the generated HTTPS URL on any device.

The root `requirements.txt` declares Python dependencies and
`.streamlit/config.toml` sets the 50 MB upload limit and presentation theme.

## Data handling

Uploaded PDFs are written only to a temporary directory for the duration of one
analysis and are deleted when analysis finishes. Reports remain in the active
Streamlit session until it is replaced or the session expires. No drawing PDF is
committed to Git.

For confidential drawings, verify the organization’s data-handling requirements
before using any third-party hosting service. A private, organization-controlled
deployment is preferable when drawings contain restricted engineering data.
