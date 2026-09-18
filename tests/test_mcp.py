import json
import subprocess
import sys
from pathlib import Path

from src.mcp_server import handle_line, handle_message


def _rpc(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    message: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    reply = handle_line(json.dumps(message))
    assert reply is not None
    return json.loads(reply)


def test_initialize_and_tool_list() -> None:
    response = _rpc("initialize")
    assert response["result"]["serverInfo"]["name"] == "consolidador-textos"
    assert "tools" in response["result"]["capabilities"]
    tools = _rpc("tools/list")["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["consolidate"]
    schema = tools[0]["inputSchema"]
    assert schema["required"] == ["recipe"]
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_call_consolidate_success(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"hello")
    recipe = tmp_path / "job.yaml"
    recipe.write_text(
        "version: 1\ninputs:\n  - folder: .\noutputs:\n  - path: out.txt\n",
        encoding="utf-8",
    )
    response = _rpc("tools/call", {"name": "consolidate", "arguments": {"recipe": str(recipe), "overwrite": True}})
    assert response["result"]["isError"] is False
    text = response["result"]["content"][0]["text"]
    assert "processed=1" in text and "exit_code=0" in text
    assert (tmp_path / "out.txt").read_bytes() == b"hello"


def test_call_consolidate_failure_is_error_result(tmp_path: Path) -> None:
    response = _rpc(
        "tools/call",
        {"name": "consolidate", "arguments": {"recipe": str(tmp_path / "missing.yaml")}},
    )
    assert response["result"]["isError"] is True
    assert _rpc("tools/call", {"name": "other", "arguments": {}})["error"]["code"] == -32602
    assert _rpc("tools/call", {"name": "consolidate", "arguments": {"recipe": 42}})["result"]["isError"] is True


def test_protocol_errors() -> None:
    assert json.loads(handle_line("not json"))["error"]["code"] == -32700
    assert _rpc("nope/method")["error"]["code"] == -32601
    assert _rpc("tools/list", request_id="abc")["id"] == "abc"


def test_stdio_smoke(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"data")
    recipe = tmp_path / "job.yaml"
    recipe.write_text(
        "version: 1\ninputs:\n  - folder: .\noutputs:\n  - path: out.txt\n",
        encoding="utf-8",
    )
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "consolidate", "arguments": {"recipe": str(recipe), "overwrite": True}}},
    ]
    result = subprocess.run(
        [sys.executable, "-m", "src.mcp_server"],
        input="\n".join(json.dumps(line) for line in lines) + "\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert [reply["id"] for reply in replies] == [1, 2, 3]
    assert replies[2]["result"]["isError"] is False
