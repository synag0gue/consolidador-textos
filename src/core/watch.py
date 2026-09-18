from __future__ import annotations

import time
from collections.abc import Callable, Iterator

from src.core.jobs import JobResult, discover_inputs, run_recipe
from src.core.recipes import Recipe
from src.extractors.registry import create_default_registry


def snapshot(recipe: Recipe) -> dict[str, tuple[int, int]]:
    registry = create_default_registry()
    state: dict[str, tuple[int, int]] = {}
    try:
        paths = discover_inputs(recipe, registry)
    except ValueError:
        paths = []
    watched = list(paths)
    if recipe.recipe_path is not None:
        watched.append(recipe.recipe_path)
    for path in watched:
        try:
            stat = path.stat()
        except OSError:
            continue
        state[str(path.resolve())] = (stat.st_size, stat.st_mtime_ns)
    return state


def snapshot_changed(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> bool:
    return before != after


def iter_runs(
    recipe: Recipe,
    interval: float = 2.0,
    overwrite: bool = False,
    ocr: str | None = None,
    max_runs: int | None = None,
    should_stop: Callable[[], bool] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> Iterator[JobResult]:
    if interval <= 0:
        raise ValueError("interval must be positive")
    runs = 0
    result = run_recipe(recipe, overwrite=overwrite, ocr=ocr)
    state = snapshot(recipe)
    yield result
    runs += 1
    while (max_runs is None or runs < max_runs) and not (should_stop and should_stop()):
        time.sleep(interval)
        try:
            fresh = snapshot(recipe)
        except Exception as exc:
            if on_error is not None:
                on_error(exc)
            continue
        if not snapshot_changed(state, fresh):
            continue
        result = run_recipe(recipe, overwrite=overwrite, ocr=ocr)
        state = snapshot(recipe)
        yield result
        runs += 1
