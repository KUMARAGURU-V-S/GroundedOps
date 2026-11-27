# GroundedOps Web Interface

This directory contains two user interfaces for GroundedOps:

1. **Streamlit Interactive Dashboard (`app.py`)**:
   - Run locally:
     ```bash
     streamlit run web/app.py
     ```
   - Features real-time query interface, model selection, citation viewer, ingestion manager, and S3 Vectors inspection.

2. **Standalone HTML/CSS Client (`static/index.html`)**:
   - Zero external dependencies.
   - Can be served via Python:
     ```bash
     python3 -m http.server 8080 --directory web/static
     ```
   - Or deployed to an Amazon S3 static hosting bucket / CloudFront CDN.
