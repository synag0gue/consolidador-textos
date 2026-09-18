# Recipe cookbook

Declarative jobs (`python -m src.cli run recipe.yaml`) for the three main
personas. Every example below was validated with `parse_recipe`. GUI
equivalents use *Archivo → Guardar/Cargar receta...*; anything the GUI
cannot apply (transforms, dedup, OCR) is reported on load, never silently
ignored.

Recipe schema: `version: 1`, `inputs` (list of `path`/`folder` with
`recursive`, `include`, `exclude`), `outputs` (`path` + `format`: txt,
docx, md, html, json, jsonl), `separator` (blank, dashes, filename,
custom) + `custom_separator`, `order` (`by: input|filename`,
`direction: asc|desc`), `transforms`, `ocr` (tesseract, easyocr),
`dedup` (off, exact, near) + `dedup_threshold`.

Exit codes: `0` success, `1` partial (skipped files or warnings),
`2` failure. Safe in scripts and CI.

---

## 1. Researcher — literature merge + LLM synthesis

Merge a folder of papers with source headings, keep a Word deliverable
and a structured file for analysis:

```yaml
version: 1
name: literature-review
inputs:
  - folder: ./papers
    recursive: true
    include: ["*.pdf", "*.docx"]
    exclude: ["*_draft.*"]
order: {by: filename, direction: asc}
separator: filename
outputs:
  - {path: ./out/review.docx}
  - {path: ./out/review.jsonl}
```

```bash
python -m src.cli run literature.yaml
```

For AI synthesis with grounding, build an offline handoff package instead
(markdown + per-block JSONL with source hashes and page numbers +
suggested citation prompt, no API keys needed):

```bash
python -m src.cli handoff ./papers -o ./out/llm-package --recursive \
  --separator filename --include "*.pdf"
```

Tip: scanned pages surface as `empty_page` warnings (exit code 1);
re-run with `--ocr tesseract` if Tesseract is installed.

---

## 2. Educator — weekly submissions with duplicate control

Collect submissions, drop byte-identical resubmits, keep reviewing the
rest. Near-duplicates are reported for human review, never auto-merged:

```yaml
version: 1
name: week-03-submissions
inputs:
  - folder: ./submissions/week-03
    include: ["*.docx", "*.pdf"]
order: {by: filename, direction: asc}
separator: filename
dedup: exact
outputs:
  - {path: ./out/week-03.docx}
```

```bash
python -m src.cli run week-03.yaml --overwrite
# Skipped duplicate ./submissions/week-03/ana-v2.docx  (stderr)
```

Keep it running all term with watch mode (reruns on every new upload;
`Ctrl+C` to stop):

```bash
python -m src.cli watch week-03.yaml --overwrite
```

GUI path: load the week folder, then *Herramientas → Revisar
duplicados...* (`Ctrl+U`) to review near-duplicate pairs side by side.

---

## 3. Developer — logs to structured output, secrets redacted

Merge service logs, newest first, strip routine lines and redact tokens
before the bundle leaves the machine:

```yaml
version: 1
name: incident-4521
inputs:
  - folder: ./logs
    include: ["*.log"]
order: {by: filename, direction: desc}
separator: filename
transforms:
  - normalize_whitespace
  - dedup_lines
  - redact:token=[A-Za-z0-9-_]{20,},password=\S+
outputs:
  - {path: ./out/incident-4521.jsonl}
```

```bash
python -m src.cli run incident.yaml && python ingest.py ./out/incident-4521.jsonl
```

Each JSONL row carries source path, sha256, block index and any
extraction warnings — ready for pandas, DuckDB or a data pipeline.
`transforms_applied` records exactly what was modified, per document.

---

## 4. Command quick reference

```bash
python -m src.cli merge <files...> -o out.docx --separator filename --recursive
python -m src.cli run recipe.yaml [--overwrite] [--ocr tesseract] [--dedup exact]
python -m src.cli handoff <inputs...> -o ./package [--transform redact:\d+]
python -m src.cli watch recipe.yaml [--interval 2.0] [--max-runs 5]
python -m src.mcp_server   # MCP stdio server: consolidate tool for AI agents
```
