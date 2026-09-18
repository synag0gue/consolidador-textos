from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from src.core.models import Block, Document


@dataclass
class TransformSpec:
    name: str
    args: tuple[str, ...] = ()


def parse_spec(spec: str) -> TransformSpec:
    name, colon, rest = spec.partition(":")
    name = name.strip()
    if not name:
        raise ValueError(f"Invalid transform spec: {spec!r}")
    args = tuple(arg for arg in (part.strip() for part in _split_args(rest)) if arg) if colon else ()
    return TransformSpec(name, args)


def _split_args(rest: str) -> list[str]:
    # Las comas dentro de {m,n} o [...] pertenecen al patrón, no separan args.
    parts: list[str] = []
    depth = 0
    in_class = False
    escaped = False
    current: list[str] = []
    for char in rest:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif in_class:
            current.append(char)
            if char == "]":
                in_class = False
        elif char == "[":
            current.append(char)
            in_class = True
        elif char == "{":
            current.append(char)
            depth += 1
        elif char == "}" and depth:
            current.append(char)
            depth -= 1
        elif char == "," and not depth:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


Transform = Callable[[Document, tuple[str, ...]], None]

_registry: dict[str, Transform] = {}


def register_transform(name: str, transform: Transform) -> None:
    _registry[name] = transform


def available_transforms() -> tuple[str, ...]:
    return tuple(sorted(_registry))


def _text_blocks(document: Document) -> list[Block]:
    return [block for block in document.blocks if block.kind in ("heading", "paragraph", "list", "page")]


def _normalize_whitespace(document: Document, args: tuple[str, ...]) -> None:
    if args:
        raise ValueError("normalize_whitespace takes no arguments")
    for block in _text_blocks(document):
        text = block.text.replace("\r\n", "\n").replace("\r", "\n")
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        block.text = re.sub(r"\n{3,}", "\n\n", text)
    for block in document.blocks:
        if block.kind == "table":
            block.attrs.table_data = [[cell.strip() for cell in row] for row in block.attrs.table_data]


def _strip_headers_footers(document: Document, args: tuple[str, ...]) -> None:
    if args:
        raise ValueError("strip_headers_footers takes no arguments")
    pages = [block for block in document.blocks if block.kind == "page"]
    if len(pages) < 2:
        return
    for edge in (0, -1):
        candidates = []
        for block in pages:
            lines = [line for line in block.text.split("\n") if line.strip()]
            candidates.append(lines[edge] if lines else None)
        repeated = candidates[0]
        if repeated and all(line == repeated for line in candidates):
            pattern = re.compile(r"(?m)^" + re.escape(repeated) + r"\n?|\n?" + re.escape(repeated) + r"$")
            for block in pages:
                block.text = pattern.sub("", block.text, count=1)


def _redact(document: Document, args: tuple[str, ...]) -> None:
    if not args:
        raise ValueError("redact requires at least one regex pattern")
    patterns = [re.compile(pattern) for pattern in args]
    for block in _text_blocks(document):
        for pattern in patterns:
            block.text = pattern.sub("[REDACTED]", block.text)
    for block in document.blocks:
        if block.kind == "table":
            redacted = []
            for row in block.attrs.table_data:
                redacted.append([_redact_cell(cell, patterns) for cell in row])
            block.attrs.table_data = redacted


def _redact_cell(cell: str, patterns: list[re.Pattern[str]]) -> str:
    for pattern in patterns:
        cell = pattern.sub("[REDACTED]", cell)
    return cell


def _dedup_lines(document: Document, args: tuple[str, ...]) -> None:
    if args:
        raise ValueError("dedup_lines takes no arguments")
    for block in _text_blocks(document):
        seen: set[str] = set()
        unique = []
        for line in block.text.split("\n"):
            if line not in seen:
                seen.add(line)
                unique.append(line)
        block.text = "\n".join(unique)


def _sort_lines(document: Document, args: tuple[str, ...]) -> None:
    if args:
        raise ValueError("sort_lines takes no arguments")
    for block in _text_blocks(document):
        block.text = "\n".join(sorted(block.text.split("\n")))


register_transform("normalize_whitespace", _normalize_whitespace)
register_transform("strip_headers_footers", _strip_headers_footers)
register_transform("redact", _redact)
register_transform("dedup_lines", _dedup_lines)
register_transform("sort_lines", _sort_lines)


def apply_transforms(documents: Sequence[Document], specs: Sequence[str]) -> None:
    for spec in specs:
        parsed = parse_spec(spec)
        transform = _registry.get(parsed.name)
        if transform is None:
            raise ValueError(f"Unknown transform: {parsed.name}")
        for document in documents:
            transform(document, parsed.args)
            document.transforms_applied.append(spec)
