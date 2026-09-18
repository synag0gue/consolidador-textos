"""Scale benchmark: extraction + consolidation + writers + dedup at 10/100/1000 files.

Usage: python benchmarks/bench_scale.py [--scales 10 100 1000]

Measurement tool, not a test: prints a timing table to stdout.
"""

from __future__ import annotations

import random
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.consolidator import build_output  # noqa: E402
from src.core.dedupe import apply_dedup  # noqa: E402
from src.core.worker import extract_files  # noqa: E402
from src.core.writers import write_output  # noqa: E402
from src.extractors.registry import create_default_registry  # noqa: E402

WORDS = [f"term{i:04d}" for i in range(2000)]


def make_corpus(root: Path, count: int, seed: int = 42) -> list[Path]:
    rng = random.Random(seed)
    paths = []
    for index in range(count):
        if index and index % 10 == 0:
            data = (root / "doc-0000.txt").read_bytes()
        elif index and index % 7 == 0:
            data = (root / "doc-0001.txt").read_bytes() + b"\nappendix"
        else:
            size = rng.randint(200, 40000)
            words = [rng.choice(WORDS) for _ in range(size // 6)]
            data = " ".join(words).encode("utf-8")
        path = root / f"doc-{index:04d}.txt"
        path.write_bytes(data)
        paths.append(path)
    return paths


def timed(label: str, func, repeats: int = 3) -> float:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        samples.append(time.perf_counter() - start)
    best = min(samples)
    print(f"  {label:<28} {best:>8.3f}s  (best of {repeats})", flush=True)
    return best


def bench_scale(count: int) -> None:
    print(f"--- {count} files ---", flush=True)
    with tempfile.TemporaryDirectory(prefix="bench-") as tmp:
        root = Path(tmp)
        paths = make_corpus(root, count)
        registry = create_default_registry()
        options = SimpleNamespace(separator_mode="filename", custom_separator="")

        extracted = list(extract_files(paths, registry))
        timed("extract", lambda: list(extract_files(paths, registry)))
        timed("build_output", lambda: build_output(extracted, options))
        timed("write txt", lambda: write_output(root / "o.txt", extracted, options, overwrite=True))
        timed("write jsonl", lambda: write_output(root / "o.jsonl", extracted, options, overwrite=True))
        timed("dedup exact", lambda: apply_dedup(extracted, "exact"))
        if count <= 100:
            timed("dedup near", lambda: apply_dedup(extracted, "near", 0.9), repeats=1)
        else:
            print("  dedup near                   skipped (O(n^2); see 100-file row)")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--scales", nargs="+", type=int, default=[10, 100, 1000])
    args = parser.parse_args()
    for count in args.scales:
        bench_scale(count)


if __name__ == "__main__":
    main()
