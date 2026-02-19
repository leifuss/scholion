#!/usr/bin/env python3
"""
Translate non-English extracted documents to English.

Supports Gemini (default), OpenAI, or Anthropic — reads whichever key is
set in .env (GEMINI_API_KEY → OPENAI_API_KEY → ANTHROPIC_API_KEY).

Sends pages in batches (default 10) to dramatically reduce API calls:
  169-page doc → ~17 calls instead of 169.

Output: data/texts/{KEY}/translation.json
  {
    "key": "...",
    "source_language": "fa",
    "target_language": "en",
    "model": "gemini-2.0-flash",
    "page_texts": {"1": "...", "2": "...", ...},
    "elements":   {"1": [{"text":"...", "label":"..."}, ...], ...}
  }

Usage:
  python scripts/08_translate.py
  python scripts/08_translate.py --keys CR7CQJJ8
  python scripts/08_translate.py --batch-size 5   # smaller batches
  python scripts/08_translate.py --force          # overwrite existing
"""

import sys
import os
import json
import time
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent

# ── Pydantic schemas (used for Gemini structured output) ───────────────────────

class ElementTranslation(BaseModel):
    n: int
    text: str

class PageTranslation(BaseModel):
    page_number: str
    page_text: str
    elements: list[ElementTranslation]

class TranslationResponse(BaseModel):
    pages: list[PageTranslation]

# ── Prompts ────────────────────────────────────────────────────────────────────

_DETECT_PROMPT = (
    "Detect the language of this text. Respond with ONLY a single ISO 639-1 "
    "language code (e.g. 'en', 'fa', 'ar', 'de', 'fr'). No explanation.\n\n"
)

_TRANSLATE_SYSTEM = """\
You are an expert academic translator specialising in Islamic history, \
cartography, historical geography, and medieval studies.

Translate the supplied pages from {source_lang} to English.

STRICT RULES:
1. Return ONLY valid JSON — no prose, no code fences.
2. Keep Arabic transliterations EXACTLY as written (ā ī ū ḥ ḍ ẓ ṣ ṭ ṯ ḏ ġ ḫ ʿ ʾ etc.).
3. Keep personal names, place names, and titles of works unchanged.
4. Keep text already in English unchanged.
5. Keep cited Arabic/Hebrew/Greek words or phrases that appear as quotations or technical terms WITHIN the translated English text unchanged (e.g. quoted Quranic phrases, transliterated loanwords). Do NOT apply this to the source-language body text — that must be translated.
6. Keep footnote/endnote markers (e.g. "1 .", "²") in position.
7. Preserve paragraph breaks and emphasis markers.
8. The "elements" array in each page output MUST have the same length as the input.
9. Context blocks (marked [CONTEXT]) are reference-only — do NOT translate or include them.
"""

_TRANSLATE_USER = """\
Translate these {n_pages} pages from {source_lang} to English.

{pages_block}

Return ONLY this JSON. IMPORTANT: page_text must be the FULL ENGLISH TRANSLATION of the page — not the original {source_lang} text:
{{
  "pages": [
    {{
      "page_number": "<page_number as string>",
      "page_text": "<ENGLISH TRANSLATION of the full page here>",
      "elements": [
        {{"n": 0, "text": "<English translation of element 0>"}},
        {{"n": 1, "text": "<English translation of element 1>"}},
        ...
      ]
    }},
    ...
  ]
}}"""

_CONTEXT_CHARS = 400   # chars of adjacent-page context at batch boundaries


# ── API helpers ────────────────────────────────────────────────────────────────

def _load_env_key(var: str) -> str:
    val = os.environ.get(var, "")
    if val:
        return val
    for env_path in [_ROOT / '.env', _ROOT / 'data' / '.env']:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith(f"{var}="):
                    return line.split("=", 1)[1].strip().strip('"\'')
    return ""


def _pick_provider() -> tuple[str, str]:
    """Return (provider_name, api_key) for first available key."""
    for provider, var, model in [
        ("gemini",    "GEMINI_API_KEY",    "gemini-2.0-flash"),
        ("openai",    "OPENAI_API_KEY",    "gpt-4o-mini"),
        ("anthropic", "ANTHROPIC_API_KEY", "claude-haiku-4-5"),
    ]:
        key = _load_env_key(var)
        if key:
            return provider, key, model
    sys.exit("No API key found. Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in .env")


def _call(provider: str, key: str, model: str,
          system: str, user: str, max_tokens: int = 8192,
          retries: int = 3) -> str:
    """Single LLM call with retry on rate-limit."""
    for attempt in range(retries):
        try:
            if provider == "gemini":
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(
                    model=model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        max_output_tokens=max_tokens,
                    ),
                )
                return resp.text

            elif provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model=model, max_tokens=max_tokens,
                    messages=[{"role": "system", "content": system},
                              {"role": "user",   "content": user}],
                )
                return resp.choices[0].message.content

            elif provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                resp = client.messages.create(
                    model=model, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return resp.content[0].text

        except Exception as exc:
            s = str(exc).lower()
            if attempt < retries - 1 and any(x in s for x in ('429', '529', 'overload', 'rate')):
                wait = 30 * (attempt + 1)
                log.warning(f"  Throttled (attempt {attempt+1}) — waiting {wait}s…")
                time.sleep(wait)
            else:
                raise
    return ''


def _salvage_json(raw: str) -> dict | None:
    """Extract JSON from LLM output that may include prose or code fences."""
    import re
    # Strip markdown code fences
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw.strip(), flags=re.MULTILINE)
    # Walk the string to find outermost balanced { ... }
    start = raw.find('{')
    if start == -1:
        return None
    depth, i = 0, start
    in_str, escape = False, False
    while i < len(raw):
        c = raw[i]
        if escape:
            escape = False
        elif c == '\\' and in_str:
            escape = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start:i + 1])
                    except Exception:
                        break
        i += 1
    return None


# ── Language detection ─────────────────────────────────────────────────────────

def detect_language(provider: str, key: str, model: str, sample: str) -> str:
    try:
        raw = _call(provider, key, model,
                    system="You are a language detector.",
                    user=_DETECT_PROMPT + sample[:800],
                    max_tokens=10, retries=2)
        lang = raw.strip().lower().split()[0][:5].rstrip('.,;:')
        return lang if len(lang) == 2 else 'unknown'
    except Exception as e:
        log.warning(f"  Language detection failed: {e}")
        return 'unknown'


# ── Batch translation ──────────────────────────────────────────────────────────

def translate_batch(provider: str, key: str, model: str, source_lang: str,
                    batch: list[dict]) -> dict[str, dict]:
    """
    Translate a batch of pages in one API call.
    batch = [{"pg": "5", "text": "...", "elements": [...],
              "prev_ctx": "...", "next_ctx": "..."}, ...]
    Returns {pg: {"page_text": "...", "elements": [...]}} for each page.
    """
    # Build the pages block — plain text input (avoids confusing JSON-output mode)
    page_parts = []
    for item in batch:
        pg   = item["pg"]
        text = item["text"]
        els  = item["elements"]
        el_in = [{"n": i, "label": e.get("label", ""), "text": e.get("text", "")}
                 for i, e in enumerate(els)]

        parts = []
        if item.get("prev_ctx"):
            parts.append(f"[CONTEXT — end of previous page:] …{item['prev_ctx'].strip()}")
        parts.append(f"=== Page {pg} (translate page_text and elements to English) ===")
        parts.append(f"page_text:\n{text}")
        if el_in:
            parts.append(f"elements: {json.dumps(el_in, ensure_ascii=False)}")
        if item.get("next_ctx"):
            parts.append(f"[CONTEXT — start of next page:] {item['next_ctx'].strip()}…")
        page_parts.append("\n".join(parts))

    pages_block = "\n\n".join(page_parts)
    system = _TRANSLATE_SYSTEM.format(source_lang=source_lang)
    user   = _TRANSLATE_USER.format(
        n_pages=len(batch),
        source_lang=source_lang,
        pages_block=pages_block,
    )

    if provider == "gemini":
        # Use structured output — guarantees valid JSON, no code fences
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                max_output_tokens=8192,
            ),
        )
        try:
            result = json.loads(resp.text)
        except Exception:
            result = _salvage_json(resp.text) or {}
            if not result:
                log.warning(f"    Gemini JSON parse failed: {resp.text[:200]!r}")
                result = {}
    else:
        try:
            raw    = _call(provider, key, model, system, user, max_tokens=8192)
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = _salvage_json(raw) or {}
            if not result:
                log.warning(f"    JSON parse failed — raw snippet: {raw[:300]!r}")

    pages_list = result.get("pages", [])
    if not pages_list and result:
        log.warning(f"    No 'pages' key — top-level keys: {list(result.keys())[:10]}")
    # Normalise: list → dict keyed by page_number
    if isinstance(pages_list, list):
        return {p["page_number"]: p for p in pages_list if "page_number" in p}
    return pages_list  # already a dict (non-Gemini providers)


# ── Per-doc translation ────────────────────────────────────────────────────────

def translate_doc(provider: str, key_str: str, model: str,
                  doc_key: str, texts_dir: Path,
                  force: bool = False, batch_size: int = 10) -> bool:

    doc_dir  = texts_dir / doc_key
    out_path = doc_dir / 'translation.json'

    # Check existing — skip only if complete AND no pages still look untranslated
    if out_path.exists() and not force:
        existing = json.loads(out_path.read_text())
        if not existing.get('partial'):
            import re as _re0
            pt_ex = existing.get('page_texts', {})
            still_foreign = [
                pg for pg, t in pt_ex.items()
                if isinstance(t, str) and len(t) > 30
                and len(_re0.findall(r'[\u0600-\u06FF\u0590-\u05FF]', t)) / len(t) > 0.25
            ]
            if not still_foreign:
                log.info(f"  {doc_key}: already translated — skipping (use --force to redo)")
                return True
            log.info(f"  {doc_key}: {len(still_foreign)} pages still untranslated — resuming")
        else:
            log.info(f"  {doc_key}: partial ({existing.get('pages_done')}/{existing.get('pages_total')} pages) — resuming")

    pt_path = doc_dir / 'page_texts.json'
    le_path = doc_dir / 'layout_elements.json'

    if not pt_path.exists():
        log.warning(f"  {doc_key}: page_texts.json not found — skipping")
        return False

    page_texts      = json.loads(pt_path.read_text())
    layout_elements = json.loads(le_path.read_text()) if le_path.exists() else {}

    # Detect language
    sample = next((v for v in page_texts.values() if isinstance(v, str) and len(v) > 100), "")
    source_lang = detect_language(provider, key_str, model, sample)
    log.info(f"  {doc_key}: detected language = {source_lang!r}")

    if source_lang in ('en', 'unknown'):
        log.info(f"  {doc_key}: English or undetected — skipping")
        return False

    # Sorted page list
    pages = sorted(
        (k for k in page_texts if isinstance(k, str) and k.isdigit()),
        key=lambda x: int(x)
    )

    # Load any existing partial progress
    existing     = json.loads(out_path.read_text()) if out_path.exists() else {}
    t_page_texts = existing.get('page_texts', {})
    t_elements   = existing.get('elements', {})

    # Filter to pages still needing translation.
    # Also re-queue pages whose "translation" is still in the source language
    # (detectable by high proportion of non-Latin script chars).
    import re as _re
    def _looks_untranslated(text: str) -> bool:
        if not text or len(text) < 30:
            return False
        foreign = len(_re.findall(r'[\u0600-\u06FF\u0590-\u05FF]', text))
        return (foreign / len(text)) > 0.25

    todo = [
        pg for pg in pages
        if pg not in t_page_texts
        or _looks_untranslated(t_page_texts.get(pg, ''))
        or force
    ]
    log.info(f"  {doc_key}: {len(pages)} pages total, {len(todo)} to translate "
             f"(batch_size={batch_size})")

    # Process in batches
    for batch_start in range(0, len(todo), batch_size):
        batch_pages = todo[batch_start:batch_start + batch_size]
        batch_num   = batch_start // batch_size + 1
        total_batches = (len(todo) + batch_size - 1) // batch_size

        log.info(f"    Batch {batch_num}/{total_batches}: pages {batch_pages[0]}–{batch_pages[-1]}")

        # Build batch items with boundary context
        batch_items = []
        for pg in batch_pages:
            pg_idx = pages.index(pg)
            raw_text = page_texts.get(pg, '') or ''
            raw_els  = layout_elements.get(pg, [])
            if not isinstance(raw_els, list):
                raw_els = []

            # Skip truly empty pages immediately
            if not raw_text.strip() and not raw_els:
                t_page_texts[pg] = raw_text
                t_elements[pg]   = raw_els
                continue

            prev_pg = pages[pg_idx - 1] if pg_idx > 0 else None
            next_pg = pages[pg_idx + 1] if pg_idx < len(pages) - 1 else None
            prev_ctx = (page_texts.get(prev_pg, '') or '')[-_CONTEXT_CHARS:] if prev_pg else ''
            next_ctx = (page_texts.get(next_pg, '') or '')[:_CONTEXT_CHARS]  if next_pg else ''

            batch_items.append({
                "pg":       pg,
                "text":     raw_text,
                "elements": raw_els,
                "prev_ctx": prev_ctx if pg == batch_pages[0] else '',  # only at boundary
                "next_ctx": next_ctx if pg == batch_pages[-1] else '',
            })

        if not batch_items:
            continue

        try:
            results = translate_batch(provider, key_str, model, source_lang, batch_items)
        except Exception as exc:
            log.error(f"    Batch {batch_num} FAILED: {exc} — keeping originals")
            for item in batch_items:
                t_page_texts[item["pg"]] = item["text"]
                t_elements[item["pg"]]   = item["elements"]
            results = {}

        # Merge results back — only write pages that were actually translated
        missing = []
        for item in batch_items:
            pg   = item["pg"]
            res  = results.get(pg, {})

            if "page_text" in res:
                translated_text = res["page_text"]
                # Fallback: if page_text is still untranslated, rebuild from elements
                if _looks_untranslated(translated_text) and res.get("elements"):
                    rebuilt = " ".join(
                        el.get("text", "") for el in res["elements"] if el.get("text")
                    )
                    if rebuilt and not _looks_untranslated(rebuilt):
                        log.warning(f"    p{pg}: page_text untranslated — rebuilt from elements")
                        translated_text = rebuilt
                t_page_texts[pg] = translated_text
                # Rebuild elements preserving all original fields
                orig_els = list(item["elements"])
                for el_out in res.get("elements", []):
                    n = el_out.get("n")
                    if isinstance(n, int) and 0 <= n < len(orig_els):
                        orig = dict(orig_els[n])
                        orig["text"] = el_out.get("text", orig.get("text", ""))
                        orig_els[n]  = orig
                t_elements[pg] = orig_els
            else:
                missing.append(pg)

        if missing:
            log.warning(f"    Batch {batch_num}: {len(missing)} pages not in LLM response — will retry: {missing}")

        # Incremental save after each batch
        pages_done = len(t_page_texts)
        partial = {
            'key':             doc_key,
            'source_language': source_lang,
            'target_language': 'en',
            'model':           model,
            'translated_at':   datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'partial':         True,
            'pages_done':      pages_done,
            'pages_total':     len(pages),
            'page_texts':      t_page_texts,
            'elements':        t_elements,
        }
        out_path.write_text(json.dumps(partial, ensure_ascii=False, indent=2))
        log.info(f"    → saved ({pages_done}/{len(pages)} pages done)")

        # Small pause between batches
        if batch_start + batch_size < len(todo):
            time.sleep(2)

    # Final save (mark complete)
    result = {
        'key':             doc_key,
        'source_language': source_lang,
        'target_language': 'en',
        'model':           model,
        'translated_at':   datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'page_texts':      t_page_texts,
        'elements':        t_elements,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    log.info(f"  {doc_key}: ✓ {len(pages)} pages → translation.json")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Translate non-English docs to English (Gemini/OpenAI/Anthropic).'
    )
    parser.add_argument('--texts-dir',   default='data/texts')
    parser.add_argument('--keys',        nargs='+', default=[],
                        help='Process only these document keys')
    parser.add_argument('--force',       action='store_true',
                        help='Overwrite existing translation.json files')
    parser.add_argument('--batch-size',  type=int, default=3,
                        help='Pages per API call (default: 3)')
    parser.add_argument('--model',       default=None,
                        help='Override model name (default: provider default)')
    args = parser.parse_args()

    texts_dir = _ROOT / args.texts_dir

    provider, api_key, default_model = _pick_provider()
    model = args.model or default_model
    log.info(f"Provider: {provider}  Model: {model}  Batch size: {args.batch_size}\n")

    # Determine keys
    if args.keys:
        keys = args.keys
    else:
        keys = sorted(
            d.name for d in texts_dir.iterdir()
            if d.is_dir() and (d / 'page_texts.json').exists()
        )

    log.info(f"Checking {len(keys)} document(s) for non-English content…\n")

    ok = err = skipped = 0
    for doc_key in keys:
        log.info(f"── {doc_key}")
        try:
            result = translate_doc(
                provider, api_key, model,
                doc_key, texts_dir,
                force=args.force,
                batch_size=args.batch_size,
            )
            if result is True:
                ok += 1
            else:
                skipped += 1
        except Exception as exc:
            log.error(f"  {doc_key}: FAILED — {exc}")
            err += 1
        print()

    print('=' * 60)
    print(f"✓ Translated: {ok}   ✗ Errors: {err}   – Skipped: {skipped}")


if __name__ == '__main__':
    main()
