from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from src.core.models import ConsolidationFile, ConsolidationOptions
from src.core.writers import create_default_writer_registry, validate_destination, write_output


PACKAGE_FILES = ("consolidated.md", "blocks.jsonl", "manifest.json", "PROMPT.md")


def _manifest(files: Sequence[ConsolidationFile], options: ConsolidationOptions) -> dict:
    documents = []
    for item in files:
        document = item.document
        documents.append(
            {
                "name": item.name,
                "path": str(document.source.path) if document else str(item.path),
                "sha256": document.source.sha256 if document else None,
                "size": document.source.size if document else None,
                "format": document.source.format if document else None,
                "block_count": len(document.blocks) if document else 0,
                "title": document.metadata.title if document else None,
                "author": document.metadata.author if document else None,
                "page_count": document.metadata.page_count if document else None,
                "warnings": [
                    {
                        "code": warning.code,
                        "message": warning.message,
                        "page_number": warning.page_number,
                    }
                    for warning in (document.warnings if document else [])
                ],
                "transforms_applied": list(document.transforms_applied) if document else [],
            }
        )
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "options": {
            "separator_mode": options.separator_mode,
            "custom_separator": options.custom_separator,
        },
        "document_count": len(files),
        "documents": documents,
    }


def _prompt(files: Sequence[ConsolidationFile], options: ConsolidationOptions) -> str:
    lines = [
        "# Suggested prompt (offline handoff)",
        "",
        "The folder contains `consolidated.md` (human-readable text),",
        "`blocks.jsonl` (one record per block with source provenance),",
        "and `manifest.json` (file hashes, order and extraction warnings).",
        "",
        "Suggested prompt to paste into your LLM:",
        "",
        "```",
        "Answer using ONLY the provided documents. For every claim, cite the",
        "source file name and, when available, the page number from blocks.jsonl.",
        "If the answer is not in the documents, say so explicitly.",
        "```",
        "",
        "## Files included",
        "",
    ]
    for item in files:
        warning_count = len(item.document.warnings) if item.document else 0
        suffix = f" ({warning_count} warning(s))" if warning_count else ""
        lines.append(f"- {item.name}{suffix}")
    flagged = [item for item in files if item.document and item.document.warnings]
    if flagged:
        lines += ["", "## Extraction warnings (content may be incomplete)", ""]
        for item in flagged:
            assert item.document is not None
            for warning in item.document.warnings:
                lines.append(f"- {item.name}: {warning.message}")
    lines += ["", f"Separator mode used: {options.separator_mode}", ""]
    return "\n".join(lines)


def build_handoff(
    files: Sequence[ConsolidationFile],
    options: ConsolidationOptions,
    out_dir: Path,
    overwrite: bool = False,
) -> list[Path]:
    if any(item.error is not None for item in files):
        raise ValueError("Cannot export failed extraction results")
    sources = [item.path for item in files]
    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError(f"Handoff destination is not a directory: {out_dir}")
    if out_dir.is_dir() and any(out_dir.resolve() == source.resolve() for source in sources):
        raise ValueError(f"Handoff destination would overwrite a source: {out_dir}")
    if out_dir.is_dir() and any((out_dir / name).exists() for name in PACKAGE_FILES) and not overwrite:
        raise FileExistsError(f"Handoff package already exists: {out_dir}")
    if not out_dir.is_dir() and out_dir.exists():
        raise ValueError(f"Handoff destination is not a directory: {out_dir}")
    out_dir.mkdir(parents=False, exist_ok=True)

    registry = create_default_writer_registry()
    targets = {name: out_dir / name for name in PACKAGE_FILES}
    for target in (targets["consolidated.md"], targets["blocks.jsonl"]):
        validate_destination(target, sources, overwrite=True)
    manifest_text = json.dumps(_manifest(files, options), ensure_ascii=False, indent=2) + "\n"
    prompt_text = _prompt(files, options)

    write_output(targets["consolidated.md"], files, options, "md", overwrite=True, registry=registry)
    try:
        write_output(targets["blocks.jsonl"], files, options, "jsonl", overwrite=True, registry=registry)
    except Exception:
        targets["consolidated.md"].unlink(missing_ok=True)
        raise
    try:
        targets["manifest.json"].write_text(manifest_text, encoding="utf-8", newline="")
        targets["PROMPT.md"].write_text(prompt_text, encoding="utf-8", newline="")
    except Exception:
        for target in targets.values():
            target.unlink(missing_ok=True)
        raise
    return [targets[name] for name in PACKAGE_FILES]
