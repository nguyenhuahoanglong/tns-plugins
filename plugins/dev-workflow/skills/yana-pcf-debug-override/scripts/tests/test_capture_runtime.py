#!/usr/bin/env python3
"""Black-box CDP capture tests using a stdlib, loopback-only fake browser."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "capture_runtime.mjs"
ORIGIN = "https://ptqatemplate.crm5.dynamics.com"
JS_URL = f"{ORIGIN}/version/webresources/cc_Test.Grid.YanaGrid/bundle.js"
CSS_URL = f"{ORIGIN}/other-version/webresources/cc_Test.Grid.YanaGrid/Styles/DatasetStyles.css"
JS_SOURCE = "globalThis.executedGridBundle = true;"
CSS_BYTES = b".editablegrid-container { color: navy; }\n"
FETCH_DECOY = b".editablegrid-container { color: red; }\n"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class FakeCdpHandler(BaseHTTPRequestHandler):
    server: "FakeCdpServer"

    def log_message(self, *_args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/json/list":
            port = self.server.server_port
            target = {
                "id": "owned-test-tab",
                "url": self.server.target_url,
                "webSocketDebuggerUrl": f"ws://{self.server.ws_host}:{port}/devtools/page/owned-test-tab",
            }
            body = json.dumps([target]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/devtools/page/owned-test-tab":
            self.send_error(404)
            return
        key = self.headers.get("Sec-WebSocket-Key")
        if not key or self.headers.get("Upgrade", "").lower() != "websocket":
            self.send_error(400)
            return
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.server.ws_connections += 1
        self.connection.settimeout(8)
        try:
            while (message := self._read_message()) is not None:
                self._handle_command(message)
        except (ConnectionError, OSError, TimeoutError, json.JSONDecodeError):
            pass

    def _read_message(self) -> dict | None:
        head = self.rfile.read(2)
        if len(head) != 2:
            return None
        opcode = head[0] & 0x0F
        if opcode == 8:
            return None
        length = head[1] & 0x7F
        if length == 126:
            length = int.from_bytes(self.rfile.read(2), "big")
        elif length == 127:
            length = int.from_bytes(self.rfile.read(8), "big")
        mask = self.rfile.read(4) if head[1] & 0x80 else b""
        payload = self.rfile.read(length)
        if len(payload) != length:
            return None
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return json.loads(payload)

    def _send(self, message: dict) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        if len(payload) < 126:
            head = bytes((0x81, len(payload)))
        elif len(payload) < 65536:
            head = bytes((0x81, 126)) + len(payload).to_bytes(2, "big")
        else:
            head = bytes((0x81, 127)) + len(payload).to_bytes(8, "big")
        self.wfile.write(head + payload)
        self.wfile.flush()

    def _event(self, method: str, params: dict) -> None:
        self._send({"method": method, "params": params})

    def _handle_command(self, message: dict) -> None:
        method = message["method"]
        params = message.get("params", {})
        self.server.calls.append((method, params))
        if method == "Debugger.getScriptSource":
            result = {"scriptSource": JS_SOURCE}
        elif method == "Network.getResponseBody":
            body = CSS_BYTES if params["requestId"] == "loaded-css" else FETCH_DECOY
            result = {"body": base64.b64encode(body).decode("ascii"), "base64Encoded": True}
        else:
            result = {}
        self._send({"id": message["id"], "result": result})
        if method == "Debugger.enable":
            self._event("Debugger.scriptParsed", {"url": JS_URL, "scriptId": "executed-js"})
            if self.server.css_mode in ("stylesheet", "fetch"):
                request_type = "Stylesheet" if self.server.css_mode == "stylesheet" else "Fetch"
                request_id = "loaded-css" if request_type == "Stylesheet" else "later-fetch"
                self._request_cycle(request_id, request_type, self.server.css_status)
            if self.server.css_mode == "stylesheet":
                self._request_cycle("later-fetch", "Fetch", 200)

    def _request_cycle(self, request_id: str, resource_type: str, status: int | None) -> None:
        self._event("Network.requestWillBeSent", {
            "requestId": request_id, "request": {"url": CSS_URL}, "type": resource_type,
        })
        response = {"url": CSS_URL}
        if status is not None:
            response["status"] = status
        self._event("Network.responseReceived", {
            "requestId": request_id, "response": response, "type": resource_type,
        })
        self._event("Network.loadingFinished", {"requestId": request_id})


class FakeCdpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), FakeCdpHandler)
        self.target_url = f"{ORIGIN}/main.aspx?test=1"
        self.ws_host = "127.0.0.1"
        self.css_mode = "stylesheet"
        self.css_status: int | None = 200
        self.calls: list[tuple[str, dict]] = []
        self.ws_connections = 0


@unittest.skipUnless(shutil.which("node"), "Node.js is required for the CDP collector")
class CaptureRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = FakeCdpServer()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def invoke(self) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        receipt = self.root / "receipt.json"
        output = self.root / "capture.json"
        receipt.write_text(json.dumps({
            "applied_at": "2020-01-01T00:00:00Z",
            "plan": {"plan_id": "fake-plan", "origin": ORIGIN,
                     "resources": [{"url": JS_URL}, {"url": CSS_URL}]},
        }), encoding="utf-8")
        process = subprocess.run([
            "node", str(SCRIPT), "--receipt", str(receipt), "--target", "owned-test-tab",
            "--output", str(output), "--port", str(self.server.server_port),
            "--duration-ms", "500",
        ], capture_output=True, text=True, timeout=12, check=False)
        return process, json.loads(output.read_text(encoding="utf-8")) if output.exists() else None

    def test_executed_script_and_loaded_stylesheet_are_captured(self) -> None:
        process, output = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        self.assertIsNotNone(output)
        self.assertEqual(output["missing_urls"], [])
        self.assertEqual(output["errors"], [])
        captured = {item["url"]: item for item in output["resources"]}
        self.assertEqual(set(captured), {JS_URL, CSS_URL})
        self.assertEqual(captured[JS_URL]["sha256"], hashlib.sha256(JS_SOURCE.encode()).hexdigest())
        self.assertEqual(captured[JS_URL]["method"], "Debugger.getScriptSource")
        self.assertEqual(captured[JS_URL]["script_id"], "executed-js")
        self.assertEqual(captured[CSS_URL]["sha256"], hashlib.sha256(CSS_BYTES).hexdigest())
        self.assertEqual(captured[CSS_URL]["method"], "Network.getResponseBody")
        self.assertEqual(captured[CSS_URL]["resource_type"], "Stylesheet")
        self.assertTrue(captured[CSS_URL]["loaded_request"])
        self.assertTrue(all(item["captured_after_apply"] for item in captured.values()))
        self.assertEqual([params["requestId"] for method, params in self.server.calls
                          if method == "Network.getResponseBody"], ["loaded-css"])
        self.assertNotIn("Page.reload", [method for method, _ in self.server.calls])

    def test_later_fetch_cannot_prove_loaded_css(self) -> None:
        self.server.css_mode = "fetch"
        process, output = self.invoke()
        self.assertEqual(process.returncode, 2, process.stderr + process.stdout)
        self.assertIsNotNone(output)
        self.assertEqual(output["missing_urls"], [CSS_URL])
        self.assertEqual([item["url"] for item in output["resources"]], [JS_URL])
        self.assertFalse(any(method == "Network.getResponseBody" for method, _ in self.server.calls))

    def test_missing_response_status_cannot_prove_loaded_css(self) -> None:
        self.server.css_status = None
        process, output = self.invoke()
        self.assertEqual(process.returncode, 2, process.stderr + process.stdout)
        self.assertIsNotNone(output)
        self.assertEqual(output["missing_urls"], [CSS_URL])
        self.assertFalse(any(method == "Network.getResponseBody" for method, _ in self.server.calls))

    def test_non_success_response_cannot_prove_loaded_css(self) -> None:
        self.server.css_status = 404
        process, output = self.invoke()
        self.assertEqual(process.returncode, 2, process.stderr + process.stdout)
        self.assertIsNotNone(output)
        self.assertEqual(output["missing_urls"], [CSS_URL])

    def test_wrong_target_origin_is_rejected_before_websocket(self) -> None:
        self.server.target_url = "https://other.example.test/main.aspx"
        process, output = self.invoke()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(output)
        self.assertIn("origin differs", process.stderr)
        self.assertEqual(self.server.ws_connections, 0)

    def test_non_loopback_websocket_is_rejected_before_connect(self) -> None:
        self.server.ws_host = "192.0.2.1"
        process, output = self.invoke()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(output)
        self.assertIn("loopback port", process.stderr)
        self.assertEqual(self.server.ws_connections, 0)


if __name__ == "__main__":
    unittest.main()
