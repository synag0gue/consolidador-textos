from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from src.core.models import Document
from src.core.transforms import register_transform


@dataclass(frozen=True)
class LlmConfig:
    endpoint: str
    api_key: str
    model: str
    timeout: float = 30.0


def config_from_env() -> LlmConfig:
    endpoint = os.environ.get("CONSOLIDAR_LLM_ENDPOINT", "").strip()
    api_key = os.environ.get("CONSOLIDAR_LLM_API_KEY", "").strip()
    model = os.environ.get("CONSOLIDAR_LLM_MODEL", "").strip()
    missing = [name for name, value in (
        ("CONSOLIDAR_LLM_ENDPOINT", endpoint),
        ("CONSOLIDAR_LLM_API_KEY", api_key),
        ("CONSOLIDAR_LLM_MODEL", model),
    ) if not value]
    if missing:
        raise ValueError(
            "LLM transforms are opt-in; set " + ", ".join(missing) + " to enable them"
        )
    return LlmConfig(endpoint.rstrip("/"), api_key, model)


def complete(prompt: str, config: LlmConfig) -> str:
    payload = json.dumps({
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        config.endpoint + "/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {config.api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"LLM request failed: {exc}") from exc
    try:
        return str(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected LLM response shape: {exc}") from exc


def _llm_summarize(document: Document, args: tuple[str, ...]) -> None:
    if args:
        raise ValueError("llm_summarize takes no arguments")
    config = config_from_env()
    for block in document.blocks:
        if block.kind not in ("heading", "paragraph", "list", "page") or not block.text.strip():
            continue
        block.text = complete(
            "Summarize the following text in one paragraph, preserving all facts, "
            "numbers and names. Reply with the summary only:\n\n" + block.text,
            config,
        )


register_transform("llm_summarize", _llm_summarize)
