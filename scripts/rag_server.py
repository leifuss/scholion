#!/usr/bin/env python3
"""
RAG chat server for the Islamic Cartography corpus.

Indexes all page_texts.json (and translation.json for non-English docs) using
BM25 keyword search, then uses Claude to answer queries with retrieved context.

Usage:
    python scripts/rag_server.py            # runs on http://localhost:8001
    python scripts/rag_server.py --port 8002

Endpoints:
    GET  /api/status          → index stats
    POST /api/chat            → {query: str} → Server-Sent Events stream
    POST /api/search          → {query: str, k: int} → top-k chunks (debug)
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from rank_bm25 import BM25Okapi

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent.parent
TEXTS_ROOT = ROOT / "data" / "texts"
INV_PATH   = ROOT / "data" / "inventory.json"

CHUNK_WORDS   = 350   # target words per chunk
CHUNK_OVERLAP = 50    # words of overlap between chunks
TOP_K         = 6     # chunks to retrieve per query
MIN_SCORE     = 1.0   # discard chunks below this BM25 score (0 = no filter)
MAX_CTX_WORDS = 3000  # max words sent to Claude

# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, key: str, page: str, chunk_words: int = CHUNK_WORDS,
               overlap: int = CHUNK_OVERLAP) -> list[dict]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = chunk_words - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_words])
        if len(chunk.split()) < 20:
            continue
        chunks.append({"key": key, "page": page, "text": chunk})
    return chunks


# ── Index building ─────────────────────────────────────────────────────────────

def load_inventory() -> dict[str, dict]:
    if not INV_PATH.exists():
        return {}
    items = json.loads(INV_PATH.read_text())
    return {it["key"]: it for it in items}


def build_index() -> tuple[list[dict], "BM25Okapi", dict]:
    """
    Scan all processed docs, build chunks list + BM25 index.
    For non-English docs, prefer translation.json page_texts if available.
    Returns (chunks, bm25, stats).
    """
    inventory = load_inventory()
    all_chunks: list[dict] = []
    stats: dict = {"docs": 0, "pages": 0, "chunks": 0, "words": 0}

    for doc_dir in sorted(TEXTS_ROOT.iterdir()):
        if not doc_dir.is_dir():
            continue
        key = doc_dir.name

        # Prefer English translation for non-English docs
        transl_path = doc_dir / "translation.json"
        pt_path     = doc_dir / "page_texts.json"

        page_texts: dict[str, str] = {}

        if transl_path.exists():
            try:
                t = json.loads(transl_path.read_text())
                if t.get("page_texts"):
                    page_texts = t["page_texts"]
            except Exception:
                pass

        if not page_texts and pt_path.exists():
            try:
                page_texts = json.loads(pt_path.read_text())
            except Exception:
                pass

        if not page_texts:
            continue

        inv_item = inventory.get(key, {})
        meta = {
            "title":   inv_item.get("title", key),
            "authors": inv_item.get("authors", ""),
            "year":    inv_item.get("year", ""),
        }

        doc_chunks = 0
        for page, text in page_texts.items():
            if not isinstance(text, str) or not text.strip():
                continue
            chunks = chunk_text(text, key, page)
            for c in chunks:
                c.update(meta)
            all_chunks.extend(chunks)
            doc_chunks += len(chunks)
            stats["pages"] += 1
            stats["words"] += len(text.split())

        if doc_chunks:
            stats["docs"] += 1
        stats["chunks"] += doc_chunks

    # Build BM25 — tokenise to lowercase words
    tokenised = [
        re.findall(r"[a-zA-ZÀ-ÿ']{2,}", c["text"].lower())
        for c in all_chunks
    ]
    bm25 = BM25Okapi(tokenised)
    print(f"Index: {stats['docs']} docs · {stats['pages']} pages · "
          f"{stats['chunks']} chunks · {stats['words']:,} words", flush=True)
    return all_chunks, bm25, stats


# ── Retrieval ──────────────────────────────────────────────────────────────────

def retrieve(query: str, chunks: list[dict], bm25: BM25Okapi,
             k: int = TOP_K, min_score: float = MIN_SCORE) -> list[dict]:
    tokens = re.findall(r"[a-zA-ZÀ-ÿ']{2,}", query.lower())
    scores = bm25.get_scores(tokens)
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    results = []
    seen_keys = set()  # deduplicate by (key, page)
    for i in top_idx:
        if scores[i] < min_score:
            break  # sorted descending — no point checking further
        c = chunks[i]
        uid = (c["key"], c["page"])
        if uid in seen_keys:
            continue
        seen_keys.add(uid)
        results.append({**c, "score": float(scores[i])})
    return results


def format_context(hits: list[dict], max_words: int = MAX_CTX_WORDS) -> str:
    parts = []
    total = 0
    for h in hits:
        # Use Harvard-style citation label so the LLM cites correctly
        author = h.get("authors", "") or h["key"]
        year   = h.get("year", "n.d.")
        doc_label = f"[{author}, {year}, p.{h['page']}]"
        chunk_words = len(h["text"].split())
        if total + chunk_words > max_words:
            remaining = max_words - total
            if remaining < 50:
                break
            snippet = " ".join(h["text"].split()[:remaining])
            parts.append(f"{doc_label}\n{snippet}…")
            break
        parts.append(f"{doc_label}\n{h['text']}")
        total += chunk_words
    return "\n\n---\n\n".join(parts)


# ── LLM streaming (Gemini / OpenAI / Anthropic — uses first available key) ─────

SYSTEM_PROMPT = """\
You are a research assistant specialising in Islamic cartography, historical geography,
and medieval Arabic/Persian geographical literature. Answer questions using ONLY the
provided corpus excerpts. Cite sources inline using Harvard author-date-page format,
e.g. (Tibbetts, 1992, p.14) — match exactly the author and year shown in the excerpt
labels. If the excerpts do not contain enough information to answer, say so clearly.
Be concise but scholarly."""


def _load_env_key(var: str) -> str:
    """Return key from os.environ, falling back to .env file."""
    val = os.environ.get(var, "")
    if val:
        return val
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{var}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _stream_gemini(user_msg: str) -> Iterator[str]:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=_load_env_key("GEMINI_API_KEY"))
    for chunk in client.models.generate_content_stream(
        model="gemini-2.0-flash",
        contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=1024,
        ),
    ):
        if chunk.text:
            yield chunk.text


def _stream_openai(user_msg: str) -> Iterator[str]:
    from openai import OpenAI
    client = OpenAI(api_key=_load_env_key("OPENAI_API_KEY"))
    with client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
    ) as stream:
        for chunk in stream:
            text = chunk.choices[0].delta.content or ""
            if text:
                yield text


def _stream_anthropic(user_msg: str) -> Iterator[str]:
    import anthropic
    client = anthropic.Anthropic(api_key=_load_env_key("ANTHROPIC_API_KEY"))
    with client.messages.stream(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_llm(query: str, context: str, sources: list[dict]) -> Iterator[str]:
    """Auto-select provider based on which API key is available (Gemini > OpenAI > Anthropic)."""

    # First yield source citations (include authors/year for Harvard formatting in UI)
    source_list = [{"key": h["key"], "page": h["page"],
                    "title": h.get("title", h["key"]),
                    "authors": h.get("authors", ""),
                    "year": h.get("year", ""),
                    "score": round(h["score"], 3)}
                   for h in sources]
    yield f"data: {json.dumps({'type': 'sources', 'sources': source_list})}\n\n"

    user_msg = f"Corpus excerpts:\n\n{context}\n\n---\n\nQuestion: {query}"

    # Pick provider
    if _load_env_key("GEMINI_API_KEY"):
        provider, streamer = "Gemini", _stream_gemini
    elif _load_env_key("OPENAI_API_KEY"):
        provider, streamer = "OpenAI", _stream_openai
    elif _load_env_key("ANTHROPIC_API_KEY"):
        provider, streamer = "Anthropic", _stream_anthropic
    else:
        yield f"data: {json.dumps({'type': 'token', 'text': 'Error: no API key found. Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in .env'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    print(f"  → using {provider}", flush=True)

    try:
        for text in streamer(user_msg):
            yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'token', 'text': f'Error ({provider}): {e}'})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="Islamic Cartography RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build index at startup
print("Building BM25 index…", flush=True)
CHUNKS, BM25_INDEX, INDEX_STATS = build_index()


@app.get("/api/status")
def status():
    return {"status": "ok", "index": INDEX_STATS}


@app.post("/api/search")
def search(body: dict):
    query = body.get("query", "")
    k     = int(body.get("k", TOP_K))
    hits  = retrieve(query, CHUNKS, BM25_INDEX, k=k)
    return {"query": query, "hits": [
        {"key": h["key"], "page": h["page"], "score": h["score"],
         "snippet": h["text"][:200]}
        for h in hits
    ]}


@app.post("/api/chat")
def chat(body: dict):
    query = body.get("query", "").strip()
    if not query:
        return {"error": "empty query"}
    hits    = retrieve(query, CHUNKS, BM25_INDEX)
    context = format_context(hits)
    return StreamingResponse(
        stream_llm(query, context, hits),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Static files (data/) — must be mounted after API routes ────────────────────
app.mount("/", StaticFiles(directory=str(ROOT / "data"), html=True), name="static")

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
