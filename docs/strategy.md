# Product Strategy: A Personal Research Library Platform for Humanists

> **Working title:** *Marginalia* — your research library, illuminated.
>
> The name evokes the scholarly tradition of marginal annotation while
> signalling that this tool adds layers of insight to the texts a
> researcher already owns.  **Caveat:** There is an existing open-source
> project called [Marginalia Search](https://search.marginalia.nu/) —
> we may need to differentiate or rename.  Alternatives under
> consideration: *Glossa* (marginal commentary), *Scholion* (Greek for
> marginal note — no known conflicts), *Quire* (a gathering of
> manuscript leaves), *Folio*, *Codex*.

## 1. The Problem

Humanities researchers — historians, philologists, art historians,
literary scholars — accumulate large personal bibliographies (100–2000
items) managed in tools like Zotero, Mendeley, or Endnote.  These tools
are adequate for *cataloguing* but poor at *understanding*:

- No full-text search across your own PDFs.
- No way to see which of your sources discuss a given topic.
- No citation-graph analysis ("what am I missing?").
- No translation support for multilingual corpora.
- No structured timeline or geographic visualisation.
- No AI-assisted reading support.
- No way to annotate and link across documents in the browser.

Commercial platforms (Semantic Scholar, Elicit, Research Rabbit) offer
some of these features but operate on *their* corpus, not *yours*.  They
cannot work with unpublished scans, grey literature, or archival
material that is the bread and butter of many humanities projects.

## 2. The Vision

**Marginalia** is a *personal research library platform* that a
humanities scholar deploys in under 15 minutes, populates from their
existing bibliography manager, and progressively enhances — from a
simple interactive dashboard, through full-text search, to AI-powered
citation discovery — all without needing to install anything locally or
understand cloud infrastructure.

### Design principles

| # | Principle | Implication |
|---|-----------|-------------|
| 1 | **Zero local install** | Everything runs on GitHub (free tier) + free cloud services. The user never opens a terminal. |
| 2 | **Progressive value** | Each stage delivers standalone utility. No stage is gated on a later one. |
| 3 | **No payment for core features** | Stages 1–4 are free. LLM-powered features (bibliography extraction, translation, Stage 5-6) need the user's own API key or a modest subscription. |
| 4 | **Humanities-first UX** | Every interface uses language and metaphors familiar to researchers, not developers. No jargon. |
| 5 | **Your data, your repo** | The researcher owns their repository. No vendor lock-in. Data is plain JSON + PDF + HTML. |
| 6 | **Works with what you have** | Zotero, Mendeley, Endnote, or a plain BibTeX file. Scanned books or born-digital PDFs. Latin, Arabic, Persian, Ottoman Turkish, or any other language. |
| 7 | **Respect copyright** | Full-text content and PDFs are access-controlled. Only the researcher (and people they grant access to) can see copyrighted material. |
| 8 | **Accessible** | All interfaces target WCAG 2.1 AA compliance. Screen reader support for explorer and reader. Academic tools used by institutions must meet accessibility standards. |

## 3. User Journey (Six Stages + Cross-Cutting Features)

```
Stage 1 ─ SETUP          "I have a GitHub account and a bibliography"
   │                      ↓  Template repo + setup wizard (15 min)
   │                         Define research scope & questions
   │
Stage 2 ─ EXPLORE         "I can browse, filter, and visualise my library"
   │                      ↓  Dashboard, timeline, map, tag cloud
   │                         Zotero / Mendeley / Endnote / BibTeX import
   │
Stage 3 ─ READ            "My PDFs are searchable and readable online"
   │                      ↓  Cloud PDF fetch, OCR, reader view
   │                         Translation, bibliography extraction (LLM)
   │
Stage 4 ─ SEARCH          "I can ask questions across my whole corpus"
   │                      ↓  Client-side full-text search (free)
   │                         Optional hosted RAG (advanced)
   │
Stage 5 ─ DISCOVER        "The tool tells me what I'm missing"
   │                      ↓  Citation graph, literature gap analysis
   │                         Automatic import suggestions
   │
Stage 6 ─ UNDERSTAND      "I get scholarly commentary on my key texts"
                          ↓  AI-generated reception history, controversy
                             mapping, supersession tracking

Cross-cutting (available from Stage 2 onward):
  ─ ANNOTATE              Notes, bookmarks, highlights, links between
                          documents. Two-way sync with Zotero.
  ─ ACCESS CONTROL        Password protection for copyrighted PDFs
                          and full-text content.
  ─ RESEARCH SCOPE        User-defined research questions and scope
                          statement that guide discovery and commentary.
```

Each stage is an incremental deployment.  The user can stop at any
stage and still have a useful tool.

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Repository (user's fork of the template)            │
│                                                             │
│  data/                                                      │
│  ├── inventory.json           ← metadata (Stages 1-2)      │
│  ├── research_scope.json      ← scope + questions (Setup)   │
│  ├── annotations.json         ← user notes/bookmarks        │
│  ├── pdfs/{key}.pdf           ← fetched from Zotero cloud   │
│  ├── texts/{key}/             ← extracted text (Stage 3)    │
│  │   ├── page_texts.json                                    │
│  │   ├── meta.json                                          │
│  │   ├── layout_elements.json                               │
│  │   ├── bibliography.json                                  │
│  │   └── pages/{001..N}.jpg                                 │
│  ├── search_index.json        ← client-side index (Stage 4) │
│  ├── citation_graph/          ← citation analysis (Stage 5) │
│  │   ├── all_references.json                                │
│  │   ├── resolved_references.json                           │
│  │   ├── gap_analysis.json                                  │
│  │   └── recommendations.json                               │
│  ├── explore.html             ← dashboard UI                │
│  ├── reader.html              ← document reader             │
│  ├── search.html              ← keyword search interface    │
│  ├── chat.html                ← RAG chat (existing)         │
│  └── index.html               ← landing page                │
│                                                             │
│  .github/workflows/                                         │
│  ├── setup.yml                ← one-time setup wizard (new) │
│  ├── zotero-sync.yml          ← periodic metadata sync      │
│  ├── extract.yml              ← PDF processing pipeline     │
│  ├── build-index.yml          ← search index generation(new)│
│  └── deploy-pages.yml         ← publish to GitHub Pages     │
│                                                             │
│  GitHub Pages (free hosting)                                │
│  └── https://{user}.github.io/{repo}/                      │
│       (public metadata + access-controlled full text)       │
└─────────────────────────────────────────────────────────────┘

External services:
  ├── Zotero web API (free) ─── metadata + PDF cloud storage
  │                              + annotation write-back
  ├── Tesseract OCR (free) ─── runs in GitHub Actions
  ├── Google Vision API ─────── optional, user's own key
  ├── OpenAlex / CrossRef ──── free scholarly metadata APIs
  └── LLM API (Gemini/Claude) ─ optional, user's own key
```

**PDF storage:** PDFs are fetched from Zotero cloud on demand during
GitHub Actions processing and are **not permanently stored in the git
repository** (this would bloat the repo).  Zotero's cloud storage is
the source of truth for PDFs.  Only extracted text, page images, and
metadata are committed to the repo.

**Alternative hosting:** If GitHub Pages limits become a constraint
(bandwidth, private repo cost), Cloudflare Pages (unlimited free
bandwidth) + Cloudflare Access (free for up to 50 users, supports
Google/GitHub login) is a viable alternative that provides real
authentication without client-side encryption.

### Cost structure

| Stage | GitHub Actions minutes | External API cost | Total |
|-------|----------------------|-------------------|-------|
| 1-2   | ~1 min/sync          | Free (Zotero)     | **Free** |
| 3 (core) | ~5 min/doc (OCR)  | Free (Tesseract)  | **Free** |
| 3 (extras) | ~2 min/doc      | ~$0.0015/page (Vision); LLM for translation/biblio | **$0–15** |
| 4     | ~2 min (index build) | Free (client-side) | **Free** |
| 5     | ~5 min               | Free (OpenAlex/CrossRef); ~$0.01/query (LLM, optional) | **Free–$2** |
| 6     | ~10 min              | ~$0.15/short text, up to ~$1–3/long monograph (LLM) | **$5–30** |

**Realistic cost scenarios** (200-document corpus):

| Scenario | Cost |
|----------|------|
| Stages 1–4 only, all born-digital PDFs | **$0** |
| Stages 1–4, 50 scanned docs needing Vision OCR (~100pp each) | **~$7.50** (Vision) |
| Full pipeline (Stages 1–6) with Gemini Flash | **~$15–25** |
| Full pipeline with Claude/GPT-4 | **~$50–100** |

**Storage note:** Page images at 150 DPI for a 200-doc corpus can reach
2–3 GB.  Git LFS on GitHub Free provides 1 GB storage + 1 GB/month
bandwidth.  Options: (a) compress images to ~30 KB/page (target), (b)
use a private repo with GitHub Pro (5 GB LFS included), or (c) serve
page images from an external CDN.  This is addressed in Stage 3 plan.

**Actions minutes note:** A 200-doc corpus with OCR uses ~1,000 Actions
minutes — half the free monthly quota.  Initial corpus processing may
span 2–3 months on the free tier, or the user can process in batches.
GitHub Actions remains free for public repos; monitor any pricing
changes for private repos.

## 5. Revenue Model (Sustainability, Not Profit)

The goal is to cover hosting costs and sustain development, not to
build a business.  Monthly subscriptions do not work for individual
academics (research budgets lack line items for small SaaS tools).

| Model | Price | What you get |
|-------|-------|-------------|
| **Free (core)** | $0 | Stages 1–4 (setup, explore, read, search). Full functionality for self-hosted users who provide their own API keys for LLM features. |
| **Donation** | Pay what you want | GitHub Sponsors / Ko-fi / Buy Me a Coffee. Acknowledgement in footer. |
| **Hosted RAG** | ~$0.01/query (pay-as-you-go) | Managed RAG endpoint — no self-hosting needed. More palatable for sporadic academic use than a monthly subscription. |
| **Institutional** | Grant-funded or DH center partnership | Multi-user support, shared corpus, custom domain. Pursue via NEH Office of Digital Humanities, AHRC (UK), or university DH center budgets. |

For sustainability beyond donations, the most realistic path is
**grant funding** (NEH-ODH, AHRC, DFG) or **institutional DH center
partnerships** — this is how most DH tools (FromThePage, Recogito)
sustain themselves.

## 6. Target Users

### Primary: Solo humanities researchers
- PhD students building a dissertation bibliography
- Postdocs managing a project corpus
- Independent scholars with large personal libraries

### Secondary: Research groups
- Seminar reading lists (shared corpus, multiple readers)
- Research projects with a defined bibliography

### Tertiary: Digital humanities practitioners
- Scholars who already use computational tools and want a customisable platform

## 7. Competitive Landscape

| Tool | Full-text search | Your PDFs | Citation graph | Annotations | AI features | Self-hosted | Standards | Free |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Zotero | (plugin) | local only | no | yes (local) | no | n/a | BibTeX | yes |
| Mendeley | basic | local only | no | yes (local) | no | no | BibTeX | yes |
| Hypothes.is | no | no | no | **yes (web)** | no | no | W3C WebAnno | yes |
| Tropy | no | photos only | no | tags, notes | no | **yes (desktop)** | JSON-LD | yes |
| Recogito | no | upload | no | **semantic (NER)** | no | yes | W3C, TEI | yes |
| FromThePage | no | upload scans | no | transcription | AI-assisted | hosted | TEI, IIIF | freemium |
| Transkribus | no | upload scans | no | in-document | **HTR models** | cloud + desktop | PAGE XML | credits |
| Semantic Scholar | yes | no (their corpus) | yes | no | yes | no | — | yes |
| Elicit | yes | no (their corpus) | partial | no | yes | no | — | freemium |
| Research Rabbit | no | no | yes | no | no | no | — | yes |
| **Marginalia** | **yes** | **yes (cloud)** | **yes** | **yes (web + Zotero)** | **yes** | **yes** | **custom → W3C** | **yes** |

The unique position: Marginalia works with *your* documents — including
scans, grey literature, and non-English texts that commercial platforms
cannot index — and syncs your reading notes back to your bibliography
manager.

**Standards gap (to address):** The DH community values interoperability.
Tropy, Recogito, and FromThePage use W3C Web Annotation, TEI, and IIIF.
Marginalia currently uses a custom JSON format for annotations.  The
roadmap should migrate to W3C Web Annotation format (v1.5) to enable
interop with Hypothes.is and Recogito, and acknowledge TEI and IIIF as
future integration points.

**Positioning: "works with, not instead of."**  Researchers already have
workflows involving some of these tools.  Marginalia should complement
them: Transkribus can feed HTR output into Marginalia; Tropy-managed
photos can be uploaded; Hypothesis annotations could be imported via
W3C Web Annotation; Obsidian users can export Marginalia annotations
to markdown.  Zotero remains the metadata backbone.

## 8. Technical Prerequisites

For the *user* (not the developer):

| Requirement | Difficulty | One-time? |
|-------------|-----------|-----------|
| GitHub account (free) | Easy — most academics have one or can create one | Yes |
| Zotero account with cloud sync | Easy — standard academic tool | Yes |
| Zotero API key (read+write) | Easy — click-through at zotero.org/settings/keys | Yes |
| (Optional) Google Vision API key | Medium — requires Google Cloud account | Yes |
| (Optional) LLM API key (Gemini/Anthropic) | Medium — for translation, bibliography extraction, Stage 5-6 | Yes |

**Note:** We request read+write Zotero API access from the start so
that annotation sync (cross-cutting) and citation import (Stage 5) work
without the user needing to reconfigure later.

## 9. Cross-Cutting Features

These features are not tied to a single stage but become available
progressively and enhance every subsequent stage.

### 9.1 User Annotations & Notes

**Available from:** Stage 2 (explorer) onward; deepens with Stage 3
(reader).

| Feature | Where | Storage |
|---------|-------|---------|
| **Bookmarks** | Explorer, Reader | `data/annotations.json` |
| **Highlights** | Reader (page text) | `data/annotations.json` |
| **Margin notes** | Reader (per-page) | `data/annotations.json` |
| **Document notes** | Explorer (per-item) | `data/annotations.json` |
| **Cross-references** | Reader ("see also" links between docs) | `data/annotations.json` |
| **Tags** | Explorer (user-created tags beyond Zotero's) | `data/annotations.json` |

**Zotero write-back:** Annotations sync to Zotero as child *notes*
(not Zotero's native PDF annotations) on the parent item, using the
Zotero web API's write endpoint.  This means notes created in
Marginalia appear in the user's Zotero library.  Zotero notes already
sync *into* Marginalia via the inventory sync.

**Sync model:** Marginalia is the source of truth for highlights, margin
notes, and cross-references.  Zotero is the source of truth for
bibliographic metadata.  Notes sync one-way from Marginalia → Zotero
(append-only, via background GitHub Action — not in the browser, due to
Zotero's 1 req/sec rate limit).  Zotero notes are imported into
Marginalia on each sync cycle.  This avoids bidirectional sync
conflicts.

**Implementation:** See `docs/plan-cross-cutting-annotations.md`.

### 9.2 Research Scope & Questions

**Available from:** Stage 1 (setup wizard) onward.

The user defines:
- **Research scope:** A 1-3 sentence description of their project
  ("Ottoman cartographic practices and their relationship to earlier
  Islamic and Ptolemaic traditions, 10th-18th century").
- **Research questions:** 2-5 specific questions they are investigating.

These are stored in `data/research_scope.json` and used by:
- **Stage 4 (Search):** Pre-populate suggested searches.
- **Stage 5 (Discovery):** Focus gap analysis on literature relevant to
  the research questions, not just the corpus in general.
- **Stage 6 (Commentary):** Orient the AI commentary toward the user's
  specific interests.

**Where the user enters them:**
- Initially in the setup wizard (Stage 1)
- Editable at any time via a "Research Scope" panel in the explorer

### 9.3 Access Control (Copyright Protection)

**Available from:** Stage 3 (when PDFs and full text become available).

Copyrighted PDFs and extracted full text must not be publicly
accessible.  GitHub Pages is public by default, so we need a
protection layer.

**Approach:**

| Layer | What it protects | Method |
|-------|-----------------|--------|
| **PDFs** | `data/pdfs/*.pdf` | Not served via GitHub Pages at all. Stored in the git repo (private or LFS) but excluded from the Pages build. The reader fetches page images, not raw PDFs. |
| **Full text** | `page_texts.json`, `search_index.json` | Client-side encryption with a user-chosen password. The JSON files are encrypted (AES-256) at build time; the browser decrypts them with the password at runtime. |
| **Page images** | `data/texts/{key}/pages/*.jpg` | Same encryption or served via a simple token-gated proxy. |
| **Metadata** | `inventory.json`, `explore.html` | Public by default (titles, authors, years are not copyrighted). User can choose to make the entire site private. |

**Recommended: Private repository** (default).  Use a GitHub *private*
repository.  GitHub Pages for private repos requires GitHub Pro
($4/month) or a GitHub Education account (free for students and
academics — the primary audience).  All content is then behind
GitHub's authentication.  **This is the default recommendation.**

**Fallback: Public repo + client-side encryption** for users on the free
GitHub tier.  Metadata (titles, authors, links) remains public.  Full
text and page images are encrypted (AES-256) at build time.  **Caveat:**
Client-side encryption is a speed bump, not a security boundary — the
decryption code and encrypted files are both publicly accessible, and
decrypted content is visible in browser DevTools.  This does not
constitute a "technical protection measure" under the DMCA.  Users are
responsible for ensuring their use of copyrighted material falls under
fair use / fair dealing / applicable scholarly exceptions.

**Alternative for free-tier users:** Do not serve full-text content or
page images via GitHub Pages at all.  Serve only metadata publicly.
Full-text search and reading require the user to run a local server
or use the Zotero cloud reader for the original PDFs.

## 10. Implementation Roadmap

| Phase | Stages | Focus | Est. effort |
|-------|--------|-------|-------------|
| **Alpha** | 1-2 + scope | Template repo, setup wizard, Zotero import, explorer, research scope | 2-3 weeks |
| **Beta** | 3 + access control | PDF fetch + extraction, reader, annotations, copyright protection | 1-2 weeks (mostly done) |
| **v1.0** | 4 | Client-side search, search UI | 1-2 weeks |
| **v1.5** | 5 + hosted RAG | Citation discovery, OpenAlex lookup, gap analysis, optional hosted RAG | 2-3 weeks |
| **v2.0** | 6 | AI commentary | 2-3 weeks |

**Note:** Annotations are a cross-cutting feature built incrementally
across Alpha (bookmarks, notes in explorer) and Beta (highlights,
margin notes in reader).  The hosted RAG option (designed in Stage 4
plan) ships in v1.5 alongside citation discovery.

## 11. Success Metrics

- **Adoption:** 10 researchers deploy a personal instance within 3 months of launch
- **Retention:** 5 of those researchers reach Stage 3 (PDF processing)
- **Word of mouth:** At least 2 researchers who deployed it recommend it to a colleague
- **Sustainability:** Donations or grant funding cover hosting costs within 6 months

## 12. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| **User abandons at setup** | High | Target ≤6 UI operations for Stage 1; evaluate OAuth onboarding app (see below); video walkthrough; concierge onboarding for first 10 users |
| GitHub Actions free tier limits (2000 min/month) | Medium | Batch processing across months; document expected usage per corpus size; monitor GitHub pricing changes |
| LLM API costs surprise users | Medium | Clear cost estimates before each operation; dry-run modes; always show expected cost before triggering |
| **Stage 5–6 hallucination risk** | Medium–High | All AI outputs must cite specific passages from the user's corpus; confidence scores on recommendations; explicit "AI-generated" labels; user can flag/dismiss bad outputs |
| **Solo developer / bus factor** | Medium | Open-source from day one; comprehensive docs; modular architecture (each stage independent); community contributions welcome |
| Non-English OCR quality | Medium | Already handle Arabic/Persian/Turkish; document limitations; Vision API as fallback |
| GitHub dependency (pricing, TOS changes) | Low–Medium | Architecture is portable: static files + Actions could move to GitLab CI + Cloudflare Pages; document migration path |
| **Zotero annotation sync conflicts** | Medium | Define clear ownership model: Marginalia is source of truth for highlights/notes; Zotero is source of truth for metadata; notes sync one-way from Marginalia → Zotero (append-only); Zotero notes import on sync |
| Copyright infringement | Medium | Private repo as default; clear fair-use documentation; never serve raw PDFs publicly |
| Annotation data loss | Low | Annotations stored in git (versioned); Zotero write-back provides secondary backup |
| **No go-to-market plan** | High | See Section 14 below |
| **Data portability** | Low | All data is plain JSON/PDF/HTML in a git repo — inherently portable; migrate annotations to W3C Web Annotation standard (v1.5) for interop |
| Git LFS storage limits | Medium | Image compression (target 30 KB/page); private repos get 5 GB LFS; document alternatives |
| GitHub Actions TOS compliance | Low | Verify OCR/LLM usage is within acceptable use; all processing is for the user's own repo |

**Setup friction — the critical risk.**  Getting a non-technical
humanities scholar from zero to a working instance is the single
biggest adoption challenge.  The Stage 1 plan targets ≤6 user-facing
operations.  If this proves insufficient, we should build a thin
onboarding web app (similar to how Netlify/Vercel handle deployment)
that uses OAuth to create the fork, set secrets, and enable Pages
automatically.  This adds a small hosted component but preserves the
"zero local install" principle.

## 13. Go-to-Market Plan

The DH community has well-established channels.  Launch strategy:

| Phase | Channel | Action |
|-------|---------|--------|
| **Pre-launch** | Personal network | Recruit 3–5 beta testers from target audience (PhD students, postdocs) |
| **Launch** | DH Slack/Discord, Mastodon (#digitalhumanities), Humanist listserv | Announcement post with demo video |
| **Conference** | DH2026, ADHO, discipline-specific conferences | Lightning talk / poster; live demo |
| **Sustained** | Blog post (Medium / DH blog), Zotero forums | Tutorial: "From Zotero to searchable corpus in 15 minutes" |
| **Word of mouth** | GitHub README, explore.html footer | "Built with Marginalia" badge; one-click fork link |

**Key metric:** 10 active instances within 3 months of launch (see
Section 11).

## 14. Future Directions (Post-v2.0)

Features identified by peer review as high-value but out of scope for
the initial roadmap:

1. **Export / Publication support.** Export annotated bibliographies,
   formatted citation lists (Chicago/MLA/Turabian), and highlighted
   passage compilations.  High value for dissertation writers.

2. **Seminar / reading group mode.** Shared annotations and discussion
   threads for 8–15 researchers reading the same texts.  See
   FromThePage for prior art.

3. **Image region annotation.** Art historians and material culture
   scholars need to annotate image regions, not just text.  IIIF
   integration would enable this.

4. **TEI/XML interoperability.** Import/export in TEI format for
   interop with the broader DH tool ecosystem.

5. **Offline / PWA support.** Service worker caching for the explorer
   and reader, enabling use in archives with poor connectivity or
   during travel.  Feasible since all data is static JSON/HTML.

6. **Non-English UI and documentation.** The target audience includes
   scholars working in Arabic, Persian, and Turkish — the interface
   should eventually support these languages.

7. **Named entity recognition (NER).** Automatic extraction of people,
   places, dates, and concepts from corpus text.  Feeds into geographic
   visualisation and improves citation discovery.  See Recogito for
   prior art.

8. **Integration with note-taking tools.** Export annotations to
   Obsidian, Notion, or Logseq markdown format.  Many researchers
   maintain a personal knowledge base outside their bibliography
   manager.  (Note: Obsidian + Zotero Integration is an increasingly
   popular competitor for the "personal research infrastructure" need.)

9. **Image/figure extraction from PDFs.** Particularly important for
   art history and cartography — extract, organise, and annotate
   figures and maps from PDFs, not just text.

10. **Reading lists / reading order.** Let the user create ordered
    reading lists for teaching or onboarding new research group members.

## 15. Open Questions

1. **Name:** "Marginalia" conflicts with Marginalia Search.  Top
   alternatives: Glossa, Scholion, Quire.  Decision needed before
   launch.

2. **Mendeley/Endnote adapters:** Build native API adapters or require
   BibTeX export as a universal fallback?

3. **Multi-collection support:** How prominent should this be in the
   initial release?  (Currently implemented but not in the template
   flow.)

4. **Mobile experience:** How well does the explorer/reader work on
   tablets/phones?  Needs testing.

5. **Collaboration model:** Should multiple researchers be able to
   contribute to the same corpus?  What does that workflow look like?
   (GitHub's fork/PR model is available but may be too developer-
   oriented for the audience.)

6. **Annotation format migration:** Plan to migrate from custom JSON to
   W3C Web Annotation standard by v1.5 for interop with Hypothes.is,
   Recogito, and other tools.  Design the internal format to be
   W3C-compatible from the start if possible.

7. **OAuth onboarding app:** Should we build a thin hosted web app
   that automates GitHub fork + secrets + Pages setup via OAuth?
   This would dramatically reduce Stage 1 friction but adds a hosted
   dependency.

---

*This document is the top-level strategy.  Each stage has its own
detailed implementation plan in `docs/plan-stage{N}-*.md`.  Cross-cutting
features have their own plans in `docs/plan-cross-cutting-*.md`.*

---

## Appendix: Peer Review Summary

This strategy was reviewed by two independent AI peer reviewers
(simulating perspectives from the DH tool and academic software
communities).  Key feedback incorporated:

**Structural changes:**
- **Go-to-market plan** added (Section 13 — was entirely missing)
- **Future directions** section added (Section 14 — export, seminar
  mode, image annotation, NER, TEI, offline/PWA, Obsidian integration)
- **Accessibility** added as Design Principle #8 (WCAG 2.1 AA)
- **Revenue model** revised: subscriptions replaced with donation/grant
  model (more realistic for academic audience)

**Risk mitigations:**
- **Onboarding friction** is the critical risk — concrete step-count
  targets (≤6 operations) and OAuth onboarding app option added
- **Private repo** elevated to default copyright strategy; client-side
  encryption downgraded to fallback with honest security assessment
- **Bus factor / sustainability** added as explicit risk
- **Zotero sync conflict model** defined (Marginalia = source of truth
  for annotations; Zotero = source of truth for metadata; one-way sync)

**Technical corrections:**
- **Cost estimates** revised upward with realistic scenarios (Vision
  OCR, LLM at scale, Git LFS storage)
- **PDF storage** clarified: PDFs not stored in git; Zotero cloud is
  source of truth
- **Cloudflare Pages + Access** documented as GitHub Pages alternative
- **Competitive landscape** expanded: Tropy, Recogito, FromThePage,
  Transkribus, Mirador, Obsidian+Zotero
- **Standards gap** (W3C Web Annotation, TEI, IIIF) acknowledged;
  pragmatic adoption strategy: simple internal format, W3C export
- **"Works with, not instead of"** positioning added for DH tool ecosystem
- **Name alternatives** expanded: Scholion and Quire (no conflicts);
  confirmed Marginalia conflicts with 4+ existing projects
- **OpenAlex coverage** limitations noted for non-English/historical
  sources (relevant to the Islamic cartography use case)
