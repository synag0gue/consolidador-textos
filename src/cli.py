from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.core.dedupe import apply_dedup
from src.core.handoff import build_handoff
from src.core.jobs import discover_inputs, run_recipe
from src.core.recipes import InputSpec, JobOptions, OutputSpec, Recipe, load_recipe
from src.core.worker import extract_files
from src.core.writers import create_default_writer_registry
from src.extractors.registry import create_default_registry


def _report_dedup(skipped, candidates, kept) -> None:
    for item in skipped:
        print(f"Skipped duplicate {item.path}", file=sys.stderr)
    for pair in candidates:
        print(
            f"Possible duplicates ({pair.ratio:.2f}): "
            f"{kept[pair.first].path} <> {kept[pair.second].path}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consolidate documents without launching the desktop UI.")
    commands = parser.add_subparsers(dest="command", required=True)
    merge = commands.add_parser("merge", help="Consolidate files or folders")
    merge.add_argument("inputs", nargs="+", type=Path)
    merge.add_argument("-o", "--output", required=True, type=Path)
    merge.add_argument("--format", choices=create_default_writer_registry().supported_formats())
    merge.add_argument("--recursive", action="store_true")
    merge.add_argument("--include", action="append")
    merge.add_argument("--exclude", action="append", default=[])
    merge.add_argument("--separator", choices=["blank", "dashes", "filename", "custom"], default="blank")
    merge.add_argument("--custom-separator", default=r"\n---\n")
    merge.add_argument("--order", choices=["input", "filename"], default="input")
    merge.add_argument("--descending", action="store_true")
    merge.add_argument("--transform", action="append", default=[])
    merge.add_argument("--ocr", choices=["tesseract", "easyocr"])
    merge.add_argument("--dedup", choices=["off", "exact", "near"], default=None)
    merge.add_argument("--dedup-threshold", type=float, default=None)
    merge.add_argument("--overwrite", action="store_true")
    run = commands.add_parser("run", help="Run a version 1 YAML or JSON recipe")
    run.add_argument("recipe", type=Path)
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--ocr", choices=["tesseract", "easyocr"])
    run.add_argument("--dedup", choices=["off", "exact", "near"], default=None)
    run.add_argument("--dedup-threshold", type=float, default=None)
    handoff = commands.add_parser("handoff", help="Build an offline LLM handoff package")
    handoff.add_argument("inputs", nargs="+", type=Path)
    handoff.add_argument("-o", "--output-dir", required=True, type=Path)
    handoff.add_argument("--recursive", action="store_true")
    handoff.add_argument("--include", action="append")
    handoff.add_argument("--exclude", action="append", default=[])
    handoff.add_argument("--separator", choices=["blank", "dashes", "filename", "custom"], default="blank")
    handoff.add_argument("--custom-separator", default=r"\n---\n")
    handoff.add_argument("--order", choices=["input", "filename"], default="input")
    handoff.add_argument("--descending", action="store_true")
    handoff.add_argument("--transform", action="append", default=[])
    handoff.add_argument("--ocr", choices=["tesseract", "easyocr"])
    handoff.add_argument("--dedup", choices=["off", "exact", "near"], default=None)
    handoff.add_argument("--dedup-threshold", type=float, default=None)
    handoff.add_argument("--overwrite", action="store_true")
    watch = commands.add_parser("watch", help="Rerun a recipe whenever its inputs change")
    watch.add_argument("recipe", type=Path)
    watch.add_argument("--interval", type=float, default=2.0)
    watch.add_argument("--max-runs", type=int, default=None)
    watch.add_argument("--overwrite", action="store_true")
    watch.add_argument("--ocr", choices=["tesseract", "easyocr"])
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            recipe = load_recipe(args.recipe)
        elif args.command == "handoff":
            options = JobOptions(args.separator, args.custom_separator)
            recipe = Recipe(
                inputs=[InputSpec(path.resolve(), args.recursive, args.include or ["*"], args.exclude) for path in args.inputs],
                outputs=[],
                options=options,
                order=args.order,
                descending=args.descending,
                transforms=args.transform,
            )
            registry = create_default_registry(ocr=args.ocr)
            paths = discover_inputs(recipe, registry)
            files = list(extract_files(paths, registry))
            if args.transform:
                from src.core.transforms import apply_transforms

                apply_transforms(
                    [item.document for item in files if item.document is not None],
                    args.transform,
                )
                for item in files:
                    if item.document is not None:
                        item.text = item.document.to_plain_text()
            for item in files:
                if item.error:
                    print(f"Skipped {item.path}: {item.error}", file=sys.stderr)
                if item.document:
                    for warning in item.document.warnings:
                        print(f"Warning {item.path}: {warning.message}", file=sys.stderr)
            successful = [item for item in files if item.error is None]
            if not successful:
                return 2
            deduped = apply_dedup(successful, args.dedup or "off", args.dedup_threshold or 0.9)
            _report_dedup(deduped.skipped_exact, deduped.candidates, deduped.kept)
            for created in build_handoff(deduped.kept, options, args.output_dir, overwrite=args.overwrite):
                print(created)
            if len(successful) != len(files) or any(
                item.document and item.document.warnings for item in successful
            ):
                return 1
            return 0
        elif args.command == "watch":
            from src.core.watch import iter_runs

            code = 0
            for result in iter_runs(
                load_recipe(args.recipe), interval=args.interval, overwrite=args.overwrite,
                ocr=args.ocr, max_runs=args.max_runs,
            ):
                for item in result.files:
                    if item.error:
                        print(f"Skipped {item.path}: {item.error}", file=sys.stderr)
                _report_dedup(result.skipped_duplicates, result.duplicate_candidates, result.exported or result.files)
                for output in result.outputs:
                    print(output, flush=True)
                code = max(code, result.exit_code)
            return code
        else:
            recipe = Recipe(
                inputs=[InputSpec(path.resolve(), args.recursive, args.include or ["*"], args.exclude) for path in args.inputs],
                outputs=[OutputSpec(args.output.absolute(), args.format or args.output.suffix)],
                options=JobOptions(args.separator, args.custom_separator),
                order=args.order,
                descending=args.descending,
                transforms=args.transform,
            )
        result = run_recipe(
            recipe, overwrite=args.overwrite, ocr=args.ocr,
            dedup=args.dedup, dedup_threshold=args.dedup_threshold,
        )
        for item in result.files:
            if item.error:
                print(f"Skipped {item.path}: {item.error}", file=sys.stderr)
            if item.document:
                for warning in item.document.warnings:
                    print(f"Warning {item.path}: {warning.message}", file=sys.stderr)
        _report_dedup(result.skipped_duplicates, result.duplicate_candidates, result.exported or result.files)
        for output in result.outputs:
            print(output)
        return result.exit_code
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
