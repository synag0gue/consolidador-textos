from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field

from src.core.models import ConsolidationFile


@dataclass(frozen=True)
class DuplicatePair:
    first: int
    second: int
    ratio: float
    first_preview: str
    second_preview: str


@dataclass
class DedupResult:
    kept: list[ConsolidationFile] = field(default_factory=list)
    skipped_exact: list[ConsolidationFile] = field(default_factory=list)
    candidates: list[DuplicatePair] = field(default_factory=list)


PREVIEW_CHARS = 200

# Prefiltro heurístico: el ratio de SequenceMatcher es O(n*m), así que los
# pares largos primero pasan por Jaccard sobre trigramas de palabras, mucho
# más barato. Los duplicados exactos siempre lo superan (Jaccard 1.0) y los
# textos cortos se comparan directamente. Solo el modo "near" (sugerencias
# de revisión, nunca borrado automático) depende de este filtro.
_TRIGRAM_FLOOR = 20
_PREFILTER_FACTOR = 0.2


def _word_trigrams(text: str) -> set[int]:
    words = text.split()
    return {hash((words[i], words[i + 1], words[i + 2])) for i in range(len(words) - 2)}


def _jaccard(left: set[int], right: set[int]) -> float:
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def _passes_prefilter(left: set[int], right: set[int], bar: float) -> bool:
    if min(len(left), len(right)) < _TRIGRAM_FLOOR:
        return True
    return _jaccard(left, right) >= bar


def content_hash(item: ConsolidationFile) -> str:
    if item.document is not None:
        return item.document.source.sha256
    return hashlib.sha256(item.text.encode("utf-8")).hexdigest()


def find_exact_groups(files: list[ConsolidationFile]) -> list[list[int]]:
    by_hash: dict[str, list[int]] = {}
    for index, item in enumerate(files):
        by_hash.setdefault(content_hash(item), []).append(index)
    return [sorted(group) for group in by_hash.values() if len(group) > 1]


def _length_bound(len_a: int, len_b: int) -> float:
    total = len_a + len_b
    return (2 * min(len_a, len_b) / total) if total else 0.0


def find_near_pairs(files: list[ConsolidationFile], threshold: float = 0.9) -> list[DuplicatePair]:
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    texts = [item.text for item in files]
    trigrams = [_word_trigrams(text) if text.strip() else set() for text in texts]
    bar = threshold * _PREFILTER_FACTOR
    pairs: list[DuplicatePair] = []
    for first in range(len(files)):
        if not texts[first].strip():
            continue
        for second in range(first + 1, len(files)):
            if not texts[second].strip():
                continue
            if _length_bound(len(texts[first]), len(texts[second])) < threshold:
                continue
            if not _passes_prefilter(trigrams[first], trigrams[second], bar):
                continue
            matcher = difflib.SequenceMatcher(None, texts[first], texts[second])
            if matcher.quick_ratio() < threshold:
                continue
            ratio = matcher.ratio()
            if ratio >= threshold:
                pairs.append(DuplicatePair(
                    first=first,
                    second=second,
                    ratio=ratio,
                    first_preview=texts[first][:PREVIEW_CHARS],
                    second_preview=texts[second][:PREVIEW_CHARS],
                ))
    pairs.sort(key=lambda pair: pair.ratio, reverse=True)
    return pairs


def apply_dedup(
    files: list[ConsolidationFile],
    mode: str = "off",
    threshold: float = 0.9,
) -> DedupResult:
    if mode not in ("off", "exact", "near"):
        raise ValueError(f"Unknown dedup mode: {mode}")
    result = DedupResult(kept=list(files))
    if mode == "off":
        return result
    if mode == "exact":
        skipped: set[int] = set()
        for group in find_exact_groups(files):
            skipped.update(group[1:])
        result.kept = [item for index, item in enumerate(files) if index not in skipped]
        result.skipped_exact = [item for index, item in enumerate(files) if index in skipped]
        return result
    result.candidates = find_near_pairs(files, threshold)
    return result
