from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from src.core import llm as _llm_plugin  # noqa: F401 - registers the opt-in llm_* transforms
from src.core.dedupe import DuplicatePair, apply_dedup
from src.core.models import ConsolidationFile
from src.core.recipes import Recipe
from src.core.transforms import apply_transforms
from src.core.worker import extract_files
from src.core.writers import create_default_writer_registry, validate_destination, write_output
from src.extractors.registry import ExtractorRegistry, create_default_registry


@dataclass
class JobResult:
    files: list[ConsolidationFile]
    outputs: list[Path] = field(default_factory=list)
    exported: list[ConsolidationFile] = field(default_factory=list)
    skipped_duplicates: list[ConsolidationFile] = field(default_factory=list)
    duplicate_candidates: list[DuplicatePair] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if not self.outputs:
            return 2
        if any(item.error or (item.document and item.document.warnings) for item in self.files):
            return 1
        return 0


def discover_inputs(recipe: Recipe, registry: ExtractorRegistry) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    outputs = [output.path.resolve() for output in recipe.outputs]
    for spec in recipe.inputs:
        if not spec.path.exists():
            raise ValueError(f"Input does not exist: {spec.path}")
        folder = spec.path.is_dir()
        candidates = sorted(spec.path.rglob("*") if spec.recursive else spec.path.glob("*")) if folder else [spec.path]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            path = candidate.resolve()
            if path == recipe.recipe_path or path in seen:
                continue
            if folder and any(path == output or (output.exists() and path.samefile(output)) for output in outputs):
                continue
            if folder and not registry.is_supported(path):
                continue
            relative = candidate.relative_to(spec.path).as_posix() if folder else candidate.name
            def matches(pattern: str) -> bool:
                return fnmatch.fnmatchcase(relative.casefold(), pattern.casefold()) or fnmatch.fnmatchcase(candidate.name.casefold(), pattern.casefold())
            if not any(matches(pattern) for pattern in spec.include) or any(matches(pattern) for pattern in spec.exclude):
                continue
            seen.add(path)
            paths.append(path)
    if recipe.order == "filename":
        paths.sort(key=lambda path: (path.name.casefold(), str(path).casefold()))
    if recipe.descending:
        paths.reverse()
    if not paths:
        raise ValueError("No matching input files")
    return paths


def run_recipe(
    recipe: Recipe,
    overwrite: bool = False,
    ocr: str | None = None,
    dedup: str | None = None,
    dedup_threshold: float | None = None,
) -> JobResult:
    mode = dedup or recipe.dedup
    threshold = dedup_threshold if dedup_threshold is not None else recipe.dedup_threshold
    if mode not in ("off", "exact", "near"):
        raise ValueError("dedup must be 'off', 'exact' or 'near'")
    if not 0.0 < threshold <= 1.0:
        raise ValueError("dedup_threshold must be a number in (0, 1]")
    registry = create_default_registry(ocr=ocr or recipe.ocr)
    writers = create_default_writer_registry()
    paths = discover_inputs(recipe, registry)
    protected = paths + ([recipe.recipe_path] if recipe.recipe_path else [])
    destinations: list[Path] = []
    for output in recipe.outputs:
        writers.get_writer(output.format)
        validate_destination(output.path, protected, overwrite)
        for previous in destinations:
            if previous.resolve() == output.path.resolve() or (
                previous.exists() and output.path.exists() and previous.samefile(output.path)
            ):
                raise ValueError("Output destinations must be distinct")
        destinations.append(output.path)
    result = JobResult(list(extract_files(paths, registry)))
    successful = [item for item in result.files if item.error is None]
    if not successful:
        return result
    if recipe.transforms:
        apply_transforms(
            [item.document for item in successful if item.document is not None],
            recipe.transforms,
        )
        for item in successful:
            if item.document is not None:
                item.text = item.document.to_plain_text()
    dedup_result = apply_dedup(successful, mode, threshold)
    result.skipped_duplicates = dedup_result.skipped_exact
    result.duplicate_candidates = dedup_result.candidates
    exportable = dedup_result.kept
    result.exported = exportable
    if not exportable:
        return result
    for output in recipe.outputs:
        validate_destination(output.path, protected, overwrite)
        write_output(output.path, exportable, recipe.options, output.format, overwrite, writers)
        result.outputs.append(output.path)
    return result
