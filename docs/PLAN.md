# Consolidador de Textos — Improvement & Expansion Plan

Final consolidated version. Earlier partial replies are superseded.

**Assessment basis:** local source inspection plus review of all 15 reference
repositories (READMEs, licenses). Performance risks are inferred from code
paths, not benchmarked. No application code was modified; an empty `docs/`
directory was created while delivering this file.

---

## 1. Current State Analysis

### 1.1 What works (keep)

- **Extractor abstraction:** ABC + extension registry is the correct seam for
  format growth — `src/extractors/base.py:15`, `src/extractors/registry.py:17`.
- **Background extraction** with cancellation and per-file progress —
  `src/core/worker.py:17-68`.
- **Partial-failure tolerance:** one corrupt file does not kill the batch —
  `src/core/worker.py:59-64`.
- **Session-local reuse:** reordering and separator changes already reuse
  extracted text; no re-extraction happens.
- **Callable core pieces exist:** `extract_file` and `build_output` are
  GUI-free; the missing piece is a stable headless job API, not code.
- **Permissive project license (MIT)** — `LICENSE:1`. Stack: PySide6,
  python-docx, pypdf (`requirements.txt`).
- **Hidden coverage to surface in docs/filters:** `.md`, `.log`, `.csv`,
  `.text` already work as plain text — `src/extractors/txt.py:18`.

### 1.2 Verified limitations

| # | Limitation | Evidence | Impact |
|---|---|---|---|
| L1 | One string per document — pages, headings, tables, provenance destroyed at extraction | `base.py:23` returns `str`; `models.py:11` holds path/name/text/error | Researchers (citations), AI grounding, archivists |
| L2 | DOCX tables silently dropped | `src/extractors/docx.py:30-33` reads only `paragraph.text` | Educators, professionals |
| L3 | Scanned PDFs look "successful" but yield empty pages | `src/extractors/pdf.py:39` `extract_text() or ""` | Silent data loss |
| L4 | Whole-file memory loads; every completed file triggers full preview rebuild + full re-concatenation | `txt.py:31`; `main_window.py:511→626`; `consolidator.py:90-95` | Large batches degrade |
| L5 | Desktop-only: no CLI, no stable headless job API | `app.py:14` imports `QApplication` directly | Developers, automation |
| L6 | No session persistence — a 300-file selection dies on crash | `models.py`, `config.py` | Large-scale users |
| L7 | Metadata = filename only | `models.py:11` | Archival, AI grounding |
| L8 | Duplicate handling is path-only, session-only | `main_window.py:470-486` | Batch folder merges |
| L9 | Cancellation only between files; close waits 1.5 s | `worker.py:51`; `main_window.py:846-849` | Slow parser can outlive shutdown |
| L10 | Save writes directly to destination; output can overwrite a source file | `main_window.py:703-714` | Data-loss risk |

### 1.3 The barrier in one sentence

The tool can only be used interactively, by hand, once — it cannot run from a
script, rerun a merge with different settings cheaply, feed a downstream
system, or prove nothing was lost in a PDF. Those gaps, not missing formats,
separate it from indispensable.

---

## 2. Reference Repositories — Verified Findings

| Repo (license) | Take for this tool | Reject |
|---|---|---|
| **nexu-io/open-design** (Apache-2.0) | **The key template:** headless core with GUI/CLI as coequal clients; filesystem as source of truth; manifest-driven optional capabilities | Agent/LLM/MCP services |
| **github/spec-kit** (MIT) | Process discipline: spec + acceptance criteria per feature | Agent runtime machinery |
| **obra/superpowers** (MIT) | "Recipe as versionable data file" convention | Agent methodology |
| **santhreal/wafrift** (MIT/Apache-2.0) | Structured JSON reports; meaningful exit codes; result caching between runs | Entire domain (Rust pentest tool) |
| **HKUDS/LightRAG** (MIT) | `source_ids` provenance model; operator-decides dedup UX (never auto-merge); paragraph-aligned chunking | Framework — mandates LLM + embeddings |
| **JaidedAI/EasyOCR** (Apache-2.0) | Best optional OCR engine; CPU mode; per-region (bbox, text, conf) provenance; lazy `Reader` | As core dep — drags in torch |
| **baidu/Unlimited-OCR** (MIT code) | PyMuPDF PDF→PNG recipe (`fitz.Matrix(dpi/72)`) only | The model — hard CUDA requirement, violates portability |
| **Aboudjem/humanizer-skill**, **blader/humanizer** (MIT) | AI-tell pattern lists as manual cleanup checklists | AI rewriting as default behavior |
| **seny-executive-assistant** (PolyForm NC), **JoshuaSeidel/ai-chief-of-staff** (custom no-derivatives — verified in its LICENSE) | Intake-metadata / pipeline-state concepts only; ai-chief-of-staff forbids code reuse | Everything else |
| **xaviervasques/chief-of-staff** (MIT) | "Honest handoff" concept | Whole stack (Ollama/LangGraph/Qdrant) — out of scope |
| **github/spec-kit**, **ayghri/i-have-adhd** | Conventions for spec discipline and action-first reporting | Runtime |
| **Humanizr/Humanizer** (.NET), **public-apis** (directory) | Nothing applicable | Entirely |

**Cross-cutting pattern (5 of 15 repos):** *headless core, GUI as one client,
declarative files drive behavior.* That is the single most valuable import.

**License notes that constrain choices:**
- Project stays MIT.
- PyMuPDF is AGPL-3.0 — shipping it as a core dependency would effectively
  force the app to AGPL. If its PDF speed is wanted later, isolate it behind
  an optional out-of-process plugin and decide licensing explicitly.
- pypdf is BSD-3; python-docx is MIT; both safe to keep.
- EasyOCR is Apache-2.0 but requires torch — optional extra only.

---

## 3. Feature Integration Strategy

Tagged [U]niversal (applies broadly) / [N]ecessary (solves a real problem) /
[R]evolutionary (creates new possibilities). Grouped to avoid overlap.

### F1. Structured Document Model — the foundation **[U+N]**

Replace `extract(path) -> str` with `extract_structured(path) -> Document`:

    Document:
      source: path, size, mtime, sha256, format, encoding
      blocks: [Block]     # heading | paragraph | table | list | page_break
      metadata: title, author, created, modified, page_count
      warnings: [Warning] # e.g. "page 7 scanned — no text layer"
    Block:
      kind, text, attrs   # level, table_data, page_number, bbox

- Fixes L1/L2/L3/L7 at the root. Every downstream use — AI grounding,
  citation, archival, publishing — needs block boundaries; string merging
  cannot provide them.
- Keep legacy `extract()` as a flatten shim so nothing breaks. DOCX: walk
  `document.element.body` to capture tables and heading styles. PDF: one
  `page` block per page; empty-text pages become warnings, never silent
  empties.
- **Extraction cache** keyed on `(sha256, extractor_version)` under
  `%APPDATA%/ConsolidadorTextos/cache/`. Reordering, separator changes and
  re-exports become instant even after app restarts (cache discipline from
  wafrift).

### F2. Output writers as a peer plugin system **[U]**

The DOCX writer is a line-per-paragraph hack (`main_window.py:734-747`).
Introduce an `OutputWriter` registry mirroring `TextExtractor`:

| Writer | Serves |
|---|---|
| `.txt` | current behavior |
| `.docx` rebuilt from blocks (headings→Word styles, tables→real tables) | Final deliverables |
| `.md` | Publishing workflows |
| `.jsonl` — one record per block with source_id, page, kind | AI/LLM systems, database ingestion |
| `.html` (self-contained) | Web submission |
| `--stdout` | Piping into other tools |

One extraction now feeds all five stated downstream destinations without
re-parsing. Streaming writers (jsonl, txt) keep memory flat on huge jobs.

### F3. Provenance & manifest sidecar **[U+N]**

Every consolidated block carries origin (LightRAG's `source_ids` model).
Emit `manifest.json` next to every output: files, hashes, order, settings,
warnings, timestamp. Benefits: archival integrity, reproducibility, audit
trail, proof-of-processing. Optional per-block source markers
(`{filename}`, page numbers) in any format.

### F4. Headless core + CLI **[R]** — highest-leverage change

Move `consolidador.core` to zero Qt imports (extraction worker moves to
QThreadPool, which PySide6 already ships), then add:

    consolidar merge <input_dir> -o out.docx --separator filename --recursive
    consolidar run recipe.yaml
    consolidar watch recipe.yaml      # Phase 3

Exit codes distinguish success / partial-with-warnings / failure (wafrift
discipline). This converts the tool from an app into a workflow component:
scripts, CI, schedulers, and other programs become users. Solves L5.

### F5. Recipes: declarative, versionable job files **[U]**

YAML (or markdown+frontmatter, the superpowers convention) capturing
inputs, filters, order, separator, transforms, outputs:

    name: weekly-submissions
    inputs:
      - folder: ./submissions
        recursive: true
        include: ["*.docx", "*.pdf"]
    order: {by: filename, direction: asc}
    separator: filename
    transforms: [strip_headers, normalize_whitespace]
    outputs:
      - {path: ./out/week3.docx}
      - {path: ./out/week3.jsonl, format: jsonl}

- Recipes make repetitive consolidation one command (pain point: batch
  automation) and are version-controllable, shareable, reviewable.
- The GUI gains "Save as recipe…"/"Load recipe…" and becomes the recipe
  editor — GUI and CLI converge on the same artifact (open-design's
  filesystem-as-source-of-truth). Sessions auto-save as recipes, solving L6.

### F6. Duplicate detection — with human review **[U+N]**

Two layers, both non-destructive (LightRAG's conflict model: list
candidates, the operator decides — never auto-merge):

- **Path-level** (exists today, session-only): extend to recipe level with
  policies: skip / keep-newest / keep-both.
- **Content-level**: exact sha256 match first (cheap). Optional near-duplicate
  pass (difflib ratio > 0.9) surfaced as a review dialog listing candidate
  pairs with previews. Educators grading submissions and researchers merging
  literature revisions hit this weekly; silent auto-merging is the wrong
  default.

### F7. OCR as an optional plugin **[N]**

Scanned PDFs are the most common silent-failure source (L3). Detection is
core (warnings in F1); conversion is optional:

- **Tier 1 (default, light):** Tesseract via pypdf-adjacent tooling or
  system call when tesseract is on PATH — no torch, no model downloads.
- **Tier 2 (opt-in):** EasyOCR for difficult scans, lazily imported, models
  in a configurable directory for offline machines.
- **Rejected:** baidu/Unlimited-OCR — CUDA-only, violates portability.
- Scan heuristic: per-page text-layer density below a threshold (e.g. < 20
  chars) raises the warning and, if OCR is enabled, the fallback.

### F8. Transform pipeline (limited, ordered, composable) **[U]**

Transforms declared in the recipe, executed in order, before rendering:

| Transform | Value |
|---|---|
| `strip_headers/footers` | PDF page headers/footers repeat per page — top noise source in consolidated PDFs |
| `normalize_whitespace` | Fixes CRLF artifacts and double spaces |
| `remove_boilerplate` | Pattern list (`from:`, `page 1 of n`) — user-editable regex library |
| `hyphenation_repair` | Undo line-break hyphenation ("consolida-\ntor") |
| `redact` | Regex → [REDACTED] before any export (privacy for student work, reports) |
| `sort_lines` / `dedup_lines` | Log and config consolidation |

All deterministic string operations — no AI. The pipeline is AI-ready
without requiring AI.

### F9. Session & safety improvements **[N]**

- **Crash-safe sessions:** append-only JSONL journal of files, order,
  settings; auto-restore on launch (L6).
- **Atomic writes:** temp file + rename on save; refuse to overwrite a
  file that is a source of the current session (L10).
- **Streamed reads:** chunked `.txt` reading instead of `read_bytes()`
  (L4); stream the JSONL writer too.
- **Parallel extraction:** QThreadPool/QRunnable sized to `cpu_count()`,
  per-file worker; consolidation stays sequential to preserve order.
- **Cancellation lifecycle:** worker checks a cancellation flag inside
  extractors (between pages/blocks, not only between files); close waits
  with bounded timeout then proceeds.

### F10. Optional AI pipeline — deliberately last **[R, opt-in]**

Only after F1–F8 exist, because AI features are transforms over blocks,
not the core:

- **Local handoff generation (no API):** produce LLM-ready packages —
  markdown with structure markers + JSONL + suggested prompt — for pasting
  into Claude/ChatGPT. Zero API keys, works offline (chief-of-staff's
  "honest handoff" without its stack).
- **Optional LLM transforms** (summarize section, translate, cleanup) via
  pluggable BYO-key providers; off by default; outputs flagged as
  AI-modified in the manifest.
- **MCP server / local HTTP endpoint (later phase):** expose
  `consolidate(recipe)` as a tool so AI agents drive the consolidator —
  the "universal connector" endgame, cheap only after the headless core
  exists (open-design daemon pattern, minus the marketplace machinery).

---

## 4. Architectural Improvements

    consolidador/
      core/            # no PySide6 imports, ever
        model.py       # Document, Block, Warning, Provenance      (F1)
        extract/       # extractors, structured + legacy adapters  (F1)
        transform.py   # ordered transform pipeline                (F8)
        recipes.py     # load/validate/execute recipe YAML         (F5)
        writers.py     # OutputWriter registry                     (F2)
        dedupe.py      # hash + fuzzy detection, review payloads   (F6)
        cache.py       # sha256-keyed extraction cache             (F1)
        session.py     # journal, restore, atomic writes           (F9)
      cli/             # argparse entry: merge | run | watch       (F4)
      plugins/         # ocr_tesseract, ocr_easyocr, llm_*         (F7, F10)
      ui/              # existing PySide6 app, thinner over time

Key decisions and rationale:

1. **GUI is a client of core, not the host.** This single rule unlocks CLI
   (F4), recipes (F5) and future MCP/server (F10) without redesign. The
   pattern that recurred across open-design, spec-kit, superpowers, wafrift.
2. **Plugins are optional extras, isolated.** OCR and LLM support ship as
   extras (`pip install consolidador[ocr]`), lazily imported, with graceful
   degradation when absent — the registry already accepts runtime
   registration (`registry.py:25`).
3. **Warnings are first-class, not exceptions.** A scanned page is not an
   error; it is a Warning on the Document that survives into the manifest
   and can be reviewed. This distinction makes silent data loss (L3)
   impossible.
4. **Pipeline stages are pure functions over the model:**
   extract → cache → transform → assemble → write. Each stage testable
   headlessly with pytest — none exist today; after the split, all of them
   can be tested without launching Qt.
5. **Additive config migration.** `AppSettings` (`config.py:44-51`) is a
   flat validated dataclass; recipes follow the same discipline — unknown
   fields preserved, versioned schema, never a breaking rewrite.
6. **Scale behavior:** memory bounded by streaming + cache; wall time
   bounded by parallel extraction across cores; UI stays responsive
   because rendering is incremental (Phase 1) and off-thread (already).

---

## 5. Implementation Roadmap

Sequencing rule: each phase depends only on the seams of the previous
phase, never on its full scope.

### Phase 1 — Trustworthy core (biggest pain-point payoff)

| # | Item | Unlocks | Why first |
|---|---|---|---|
| 1.1 | Structured Document model (F1) + DOCX tables + PDF scan warnings | Everything; fixes L2/L3 | Correctness before features |
| 1.2 | Atomic saves + streamed text reads (F9) | Reliability at any scale | Trivial cost, removes worst L4/L10 failure modes |
| 1.3 | pytest suite for core (fixtures: docx with tables, scanned pdf, cp1252 txt) | Safe refactoring | No tests exist today |
| 1.4 | Crash-safe session journal (F9) | Large-scale trust | Highest-value UX fix |
| 1.5 | Incremental preview append instead of full rebuild | Perceived speed for 100+ file sessions | Local change at `main_window.py:511` |

Exit criteria: no silent content loss (tables, scans); 1,000-file load does
not degrade UI; crash mid-batch → session restorable.

### Phase 2 — Open the core up (reach + automation)

| # | Item | Unlocks |
|---|---|---|
| 2.1 | Headless core split — core/ stops importing PySide6; worker to QThreadPool | F4 prerequisite |
| 2.2 | CLI: consolidar merge/run | Scripts, CI, schedulers; developers + batch users |
| 2.3 | Writers registry (F2): md, jsonl, json, html + structured docx | All five downstream destinations |
| 2.4 | Recipes v1 (F5) + GUI Save/Load recipe | Repeatable jobs; GUI/CLI converge |
| 2.5 | Content dedup with review UI (F6) | Educators, literature merges |
| 2.6 | Transforms v1 (F8): whitespace, headers/footers, boilerplate, redact | Output quality |

Exit criteria: consolidar run recipe.yaml reproduces a GUI session
byte-identically (diff-verified); jsonl export round-trips into
pandas/duckdb.

### Phase 3 — Reach and intelligence

| # | Item | Notes |
|---|---|---|
| 3.1 | OCR tier 1 (Tesseract, optional, PATH-detected) | Detected scans trigger fallback; no torch |
| 3.2 | OCR tier 2 (EasyOCR extra, lazy import, offline model dir) | Hard scans, still optional |
| 3.3 | AI handoff packages (markdown + JSONL + suggested prompt) | LLM-ready output without any API — offline |
| 3.4 | Optional LLM transforms (BYO key, off by default, provenance-flagged) | AI-assisted cleanup/summary per block |
| 3.5 | Watch mode (consolidar watch recipe.yaml) | Continuous folders for educators/researchers |
| 3.6 | MCP server / local HTTP endpoint | AI agents as first-class clients |

### Phase 4 — Polish and ecosystem

- Packaging: one-file PyInstaller exe; MSIX/Store later.
- Accessibility: keyboard-only operation, high-contrast audit; i18n files
  (UI is currently Spanish-only — `main_window.py:104`).
- Docs: recipe cookbook per persona (researcher / educator / developer).
- Performance benchmark harness: a recipe + script generating N synthetic
  files (10 / 100 / 1000) with timing, so scale claims are measured, not
  assumed.
- Optional: PyMuPDF-based fast PDF plugin — only as an out-of-process
  extra with an explicit AGPL decision (see §2 license notes).

---

## 6. Answers to the Key Framing Questions

**What makes it indispensable for each persona?**
Researchers: provenance + manifest + structured output (citable, auditable).
Educators: recipes + dedup review + folder watch (weekly submissions in one
command). Professionals: structured docx/html exports + redaction
(deliverable-grade output). Developers: CLI + JSONL + stdout + exit codes
(a Unix-friendly component).

**Which features expand the work types without redesign?**
The Document model + writer registry + recipe format. New use cases become
new recipes, not new code paths.

**How do we keep simplicity and speed as scale grows?**
Default path stays three clicks; power lives in recipes; extraction is
cached, parallel, and streamed; preview is incremental. Complexity lives
behind the recipe schema, never in the main window.

**What do "universal connector" and "multitasking" mean here?**
Connector: everything is a file in or a file out — extractors and writers
are symmetric registries, recipes are declarative, the core is callable
from GUI, CLI, scripts, and eventually MCP. Multitasking: parallel
extraction, non-blocking UI, watch mode, cache-backed reruns.

**Which integrations matter most?** CLI first (everything can call it),
JSONL/MD writers (AI + databases), manifest (archival), then MCP (agents).

**What preserves flexibility for unanticipated workflows?**
The pure-function pipeline over a structured model with additive,
versioned schemas. Any future capability — new format, new transform, new
sink, new interface — slots into an existing seam.

**Which pain point unlocks the most value first?**
Metadata preservation + extraction honesty (F1): it is the root of the
quality problem and the prerequisite for dedup, AI grounding, archival,
and citations. Batch automation (F4/F5) is the close second and the fastest
productivity win for every persona.

---

## 7. Immediate next steps (this week)

1. Accept/reject the Document model sketch (F1) — it constrains everything.
2. Write the pytest skeleton with the three fixture documents (1.3).
3. Implement atomic save + streamed txt reading (1.2) — small, immediate
   safety win.
4. Open tracking issues for Phase 1 items using the acceptance criteria in
   §5 as issue descriptions.
