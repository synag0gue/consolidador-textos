import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from src.core.llm import complete, config_from_env
from src.core.models import Block, BlockAttributes, Document, DocumentSource
from src.core.transforms import apply_transforms


class _Handler(BaseHTTPRequestHandler):
    response_body = b"{}"
    status = 200
    seen: list[dict] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        type(self).seen.append(json.loads(self.rfile.read(length) or b"{}"))
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(type(self).response_body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def api():
    _Handler.seen = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _doc(tmp_path: Path) -> Document:
    path = tmp_path / "s.txt"
    path.write_bytes(b"x")
    return Document(
        DocumentSource.from_path(path),
        blocks=[
            Block("paragraph", "Long text here"),
            Block("table", attrs=BlockAttributes(table_data=[["a"]])),
            Block("paragraph", "   "),
        ],
    )


def test_llm_summarize_replaces_text_blocks(api: HTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _Handler.response_body = json.dumps({"choices": [{"message": {"content": "Summary."}}]}).encode()
    _Handler.status = 200
    monkeypatch.setenv("CONSOLIDAR_LLM_ENDPOINT", f"http://127.0.0.1:{api.server_port}")
    monkeypatch.setenv("CONSOLIDAR_LLM_API_KEY", "test-key")
    monkeypatch.setenv("CONSOLIDAR_LLM_MODEL", "test-model")

    document = _doc(tmp_path)
    apply_transforms([document], ["llm_summarize"])

    assert document.blocks[0].text == "Summary."
    assert document.blocks[1].attrs.table_data == [["a"]]
    assert document.blocks[2].text == "   "
    assert document.transforms_applied == ["llm_summarize"]
    sent = _Handler.seen[0]
    assert sent["model"] == "test-model"
    assert "Long text here" in sent["messages"][0]["content"]


def test_llm_requires_opt_in_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONSOLIDAR_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("CONSOLIDAR_LLM_API_KEY", raising=False)
    monkeypatch.delenv("CONSOLIDAR_LLM_MODEL", raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        config_from_env()
    with pytest.raises(ValueError, match="opt-in"):
        apply_transforms([_doc(tmp_path)], ["llm_summarize"])


def test_llm_bad_response_shape(api: HTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _Handler.response_body = b'{"unexpected": true}'
    _Handler.status = 200
    monkeypatch.setenv("CONSOLIDAR_LLM_ENDPOINT", f"http://127.0.0.1:{api.server_port}")
    monkeypatch.setenv("CONSOLIDAR_LLM_API_KEY", "k")
    monkeypatch.setenv("CONSOLIDAR_LLM_MODEL", "m")
    with pytest.raises(ValueError, match="Unexpected LLM response"):
        apply_transforms([_doc(tmp_path)], ["llm_summarize"])


def test_llm_connection_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONSOLIDAR_LLM_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("CONSOLIDAR_LLM_API_KEY", "k")
    monkeypatch.setenv("CONSOLIDAR_LLM_MODEL", "m")
    with pytest.raises(ValueError, match="LLM request failed"):
        complete("hi", config_from_env())
