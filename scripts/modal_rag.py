#!/usr/bin/env python3
"""
Modal deployment for the Islamic Cartography RAG server.

Serves the BM25 + Claude chat API as a persistent Modal web endpoint.
Cold-start (first request after idle) takes ~10-15s to load the index.
Subsequent requests are fast (<1s retrieval + Claude streaming).

Usage:
    modal deploy scripts/modal_rag.py          # deploy (get a permanent URL)
    modal serve  scripts/modal_rag.py          # temporary URL for testing

Setup (one-time):
    pip install modal
    modal setup
    modal secret create islamic-cartography \
        ANTHROPIC_API_KEY=sk-ant-...

After deploying, copy the printed URL into data/corpus_config.json:
    { "rag_api": "https://leifuss--islamic-cartography-rag-serve.modal.run/api" }
"""

import modal

# ── Image ─────────────────────────────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.110.0",
        "uvicorn>=0.29.0",
        "rank-bm25>=0.2.2",
        "anthropic>=0.25.0",
        "python-dotenv>=1.0.0",
    )
)

app = modal.App("islamic-cartography-rag", image=image)

# ── Mount the repo's data/texts/ directory into the container ─────────────────
# This reads from your local checkout when using `modal serve`, and from
# a Modal Volume when deployed. For deploy, run `modal_rag_upload.py` first
# (or use the GitHub Actions workflow to keep data fresh).
data_mount = modal.Mount.from_local_dir(
    "/Users/leifuss/Documents/projects/claude code/islamic-cartography-pipeline/data",
    remote_path="/app/data",
    condition=lambda path: not any(
        path.endswith(ext) for ext in [".pdf", ".docling.json", "docling.md"]
    ),
)

# ── ASGI app ──────────────────────────────────────────────────────────────────
@app.function(
    secrets=[modal.Secret.from_name("islamic-cartography")],
    mounts=[data_mount],
    # Keep one container warm to avoid cold starts on every request
    # Remove this line if you want to save credits (accept cold starts)
    keep_warm=1,
    timeout=300,
)
@modal.asgi_app()
def serve():
    """Serve the RAG FastAPI app."""
    import sys
    sys.path.insert(0, "/app")

    # Point the server at the mounted data directory
    import os
    os.environ.setdefault("TEXTS_ROOT", "/app/data/texts")
    os.environ.setdefault("INV_PATH",   "/app/data/inventory.json")

    # Import and return the FastAPI app from rag_server
    # We need to add the scripts dir to path
    sys.path.insert(0, "/app/scripts")

    # Dynamically patch ROOT before importing rag_server
    import importlib, types
    from pathlib import Path

    # Monkeypatch ROOT so rag_server finds /app/data
    import rag_server
    rag_server.ROOT       = Path("/app")
    rag_server.TEXTS_ROOT = Path("/app/data/texts")
    rag_server.INV_PATH   = Path("/app/data/inventory.json")

    # Rebuild the index with patched paths
    rag_server._INDEX = None  # force rebuild on first request

    return rag_server.app
