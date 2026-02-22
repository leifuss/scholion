#!/usr/bin/env python3
"""
Modal deployment for the Scholion RAG server.

Serves the BM25 + Claude chat API as a persistent Modal web endpoint.
Indexes all collections under data/collections/*/texts/ at startup.
Cold-start (first request after idle) takes ~10-15s to load the index.
Subsequent requests are fast (<1s retrieval + Claude streaming).

Usage:
    modal deploy scripts/modal_rag.py          # deploy (get a permanent URL)
    modal serve  scripts/modal_rag.py          # temporary URL for testing

Setup (one-time):
    pip install modal
    modal setup
    modal secret create scholion-rag \
        ANTHROPIC_API_KEY=sk-ant-...

After deploying, copy the printed URL into each collection's corpus_config.json:
    { "rag_api": "https://leifuss--scholion-rag-serve.modal.run" }
"""

import modal
from pathlib import Path

ROOT = Path(__file__).parent.parent

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

app = modal.App("scholion-rag", image=image)

# ── Mount the repo's data/ directory into the container ───────────────────────
# Excludes large binaries; the processed JSON/image files are included.
data_mount = modal.Mount.from_local_dir(
    str(ROOT / "data"),
    remote_path="/app/data",
    condition=lambda path: not any(
        path.endswith(ext) for ext in [".pdf", ".docling.json", "docling.md"]
    ),
)

scripts_mount = modal.Mount.from_local_dir(
    str(ROOT / "scripts"),
    remote_path="/app/scripts",
)

# ── ASGI app ──────────────────────────────────────────────────────────────────
@app.function(
    secrets=[modal.Secret.from_name("scholion-rag")],
    mounts=[data_mount, scripts_mount],
    # Keep one container warm to avoid cold starts on every request.
    # Remove this line to save credits (accept cold starts).
    keep_warm=1,
    timeout=300,
)
@modal.asgi_app()
def serve():
    """Serve the RAG FastAPI app."""
    import sys
    sys.path.insert(0, "/app/scripts")

    import rag_server
    from pathlib import Path
    # Ensure ROOT points to the mounted app directory
    rag_server.ROOT             = Path("/app")
    rag_server.COLLECTIONS_ROOT = Path("/app/data/collections")
    rag_server.EMB_CACHE        = Path("/app/data/.embedding_cache.npz")

    # Force index rebuild with corrected paths
    rag_server._INDEX_BUILT = False

    return rag_server.app
