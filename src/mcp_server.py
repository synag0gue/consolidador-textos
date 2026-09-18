from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SERVER_VERSION = "0.1.0"


def _error(code: int, message: str, request_id: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_spec() -> dict:
    return {
        "name": "consolidate",
        "description": "Run a version 1 recipe file and write its outputs",
        "inputSchema": {
            "type": "object",
            "required": ["recipe"],
            "properties": {
                "recipe": {"type": "string", "description": "Absolute path to a recipe YAML file"},
                "overwrite": {"type": "boolean", "default": False},
                "ocr": {"type": "string", "enum": ["tesseract", "easyocr"]},
            },
        },
    }


def _call_consolidate(arguments: Any) -> dict:
    from src.core.jobs import run_recipe
    from src.core.recipes import load_recipe

    if not isinstance(arguments, dict) or not isinstance(arguments.get("recipe"), str):
        raise ValueError("arguments.recipe must be a recipe file path string")
    if arguments.get("ocr") not in (None, "tesseract", "easyocr"):
        raise ValueError("arguments.ocr must be 'tesseract' or 'easyocr'")
    result = run_recipe(
        load_recipe(Path(arguments["recipe"])),
        overwrite=bool(arguments.get("overwrite", False)),
        ocr=arguments.get("ocr"),
    )
    skipped = sum(1 for item in result.files if item.error)
    warnings = sum(len(item.document.warnings) for item in result.files if item.document)
    summary = [
        f"processed={len(result.files)} outputs={len(result.outputs)} "
        f"skipped={skipped} warnings={warnings} exit_code={result.exit_code} "
        f"duplicates_skipped={len(result.skipped_duplicates)} "
        f"duplicate_candidates={len(result.duplicate_candidates)}"
    ]
    summary += [str(output) for output in result.outputs]
    return {"content": [{"type": "text", "text": "\n".join(summary)}], "isError": result.exit_code == 2}


def handle_message(message: Any) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
        return _error(-32600, "Invalid Request", message.get("id") if isinstance(message, dict) else None)
    method = message["method"]
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "consolidador-textos", "version": SERVER_VERSION},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [_tool_spec()]}}
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "consolidate":
            return _error(-32602, "Unknown tool", request_id)
        try:
            return {"jsonrpc": "2.0", "id": request_id, "result": _call_consolidate(params.get("arguments"))}
        except (OSError, ValueError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True},
            }
    return _error(-32601, f"Method not found: {method}", request_id)


def handle_line(line: str) -> str | None:
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return json.dumps(_error(-32700, "Parse error", None))
    response = handle_message(message)
    return json.dumps(response) if response is not None else None


def serve() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = handle_line(line)
        if reply is not None:
            print(reply, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(serve())
