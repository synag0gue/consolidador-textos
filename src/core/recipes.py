from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.ocr import available_ocr
from src.core.transforms import available_transforms, parse_spec as parse_transform_spec


@dataclass
class JobOptions:
    separator_mode: str = "blank"
    custom_separator: str = r"\n---\n"


@dataclass
class InputSpec:
    path: Path
    recursive: bool = False
    include: list[str] = field(default_factory=lambda: ["*"])
    exclude: list[str] = field(default_factory=list)


@dataclass
class OutputSpec:
    path: Path
    format: str


@dataclass
class Recipe:
    inputs: list[InputSpec]
    outputs: list[OutputSpec]
    options: JobOptions = field(default_factory=JobOptions)
    order: str = "input"
    descending: bool = False
    recipe_path: Path | None = None
    transforms: list[str] = field(default_factory=list)
    ocr: str | None = None
    dedup: str = "off"
    dedup_threshold: float = 0.9


def _mapping(value: Any, allowed: set[str], context: str) -> dict:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be an object")
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"Unknown {context} fields: {', '.join(sorted(unknown))}")
    return value


def _text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _patterns(value: Any, context: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{context} must be a list of non-empty strings")
    return value


def parse_recipe(data: Any, base: Path) -> Recipe:
    data = _mapping(data, {"version", "name", "inputs", "outputs", "separator", "custom_separator", "order", "transforms", "ocr", "dedup", "dedup_threshold"}, "recipe")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Recipe version must be 1")
    if "name" in data:
        _text(data["name"], "name")
    for key in ("inputs", "outputs"):
        if not isinstance(data.get(key), list) or not data[key]:
            raise ValueError(f"{key} must be a non-empty list")
    inputs = []
    for raw in data["inputs"]:
        entry = _mapping(raw, {"path", "folder", "recursive", "include", "exclude"}, "input")
        if ("path" in entry) == ("folder" in entry):
            raise ValueError("Each input requires exactly one path or folder")
        path = base / _text(entry.get("path", entry.get("folder")), "input path")
        if "folder" in entry and not path.is_dir():
            raise ValueError(f"Input folder does not exist: {path}")
        recursive = entry.get("recursive", False)
        if not isinstance(recursive, bool):
            raise ValueError("recursive must be a boolean")
        inputs.append(InputSpec(path.resolve(), recursive,
                                _patterns(entry.get("include", ["*"]), "include"),
                                _patterns(entry.get("exclude", []), "exclude")))
    outputs = []
    for raw in data["outputs"]:
        entry = _mapping(raw, {"path", "format"}, "output")
        path = (base / _text(entry.get("path"), "output path")).resolve()
        format = _text(entry.get("format", path.suffix), "output format").lower().lstrip(".")
        outputs.append(OutputSpec(path, format))
    mode = data.get("separator", "blank")
    if not isinstance(mode, str) or mode not in {"blank", "dashes", "filename", "custom"}:
        raise ValueError("Invalid separator mode")
    custom = data.get("custom_separator", r"\n---\n")
    if not isinstance(custom, str):
        raise ValueError("custom_separator must be a string")
    order = _mapping(data.get("order", {}), {"by", "direction"}, "order")
    by, direction = order.get("by", "input"), order.get("direction", "asc")
    if by not in ("input", "filename") or direction not in ("asc", "desc"):
        raise ValueError("order requires by: input/filename and direction: asc/desc")
    transforms = data.get("transforms", [])
    if not isinstance(transforms, list) or not all(isinstance(item, str) and item.strip() for item in transforms):
        raise ValueError("transforms must be a list of non-empty strings")
    for spec in transforms:
        parsed = parse_transform_spec(spec)
        if parsed.name not in available_transforms():
            raise ValueError(f"Unknown transform: {parsed.name}")
    ocr = data.get("ocr")
    if ocr is not None:
        if not isinstance(ocr, str) or ocr not in available_ocr():
            raise ValueError(f"Unknown OCR provider: {ocr}")
    dedup = data.get("dedup", "off")
    if dedup not in ("off", "exact", "near"):
        raise ValueError("dedup must be 'off', 'exact' or 'near'")
    threshold = data.get("dedup_threshold", 0.9)
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0.0 < threshold <= 1.0:
        raise ValueError("dedup_threshold must be a number in (0, 1]")
    return Recipe(inputs, outputs, JobOptions(mode, custom), by, direction == "desc", transforms=transforms, ocr=ocr,
                  dedup=dedup, dedup_threshold=float(threshold))


def load_recipe(path: Path) -> Recipe:
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid recipe YAML: {exc}") from exc
    recipe = parse_recipe(data, path.resolve().parent)
    recipe.recipe_path = path.resolve()
    return recipe


def dump_recipe(recipe: Recipe, path: Path) -> None:
    import yaml

    data: dict = {
        "version": 1,
        "inputs": [{"path": str(spec.path)} for spec in recipe.inputs],
        "outputs": [
            {"path": str(output.path), "format": output.format.lower().lstrip(".")}
            for output in recipe.outputs
        ],
        "separator": recipe.options.separator_mode,
    }
    if recipe.options.separator_mode == "custom":
        data["custom_separator"] = recipe.options.custom_separator
    if recipe.order != "input" or recipe.descending:
        data["order"] = {
            "by": recipe.order,
            "direction": "desc" if recipe.descending else "asc",
        }
    if recipe.transforms:
        data["transforms"] = list(recipe.transforms)
    if recipe.ocr is not None:
        data["ocr"] = recipe.ocr
    if recipe.dedup != "off":
        data["dedup"] = recipe.dedup
    if recipe.dedup_threshold != 0.9:
        data["dedup_threshold"] = recipe.dedup_threshold
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
