import contextlib
import importlib.util
import io
import json
import os
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("device_simulator", Path(__file__).with_name("main.py"))
simulator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulator)


class GatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path != "/device-events":
            return self.respond(404, {})
        if self.server.force_event_status:
            return self.respond(self.server.force_event_status, {})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.headers.get("Authorization") != "Bearer device-secret":
            return self.respond(401, {})
        if "occurredAt" not in body:
            return self.respond(400, {})
        event_id = body["externalEventId"]
        existing = self.server.events.get(event_id)
        if existing:
            if self.server.change_duplicate_id:
                return self.respond(200, {**existing, "id": str(uuid.uuid4())})
            return self.respond(200, existing)
        response = {**body, "id": str(uuid.uuid4()), "receivedAt": "2026-01-01T00:00:00Z"}
        self.server.events[event_id] = response
        return self.respond(201, response)

    def do_GET(self):
        if not self.path.startswith("/devices/") or not self.path.endswith("/events?limit=100"):
            return self.respond(404, {})
        if self.headers.get("Authorization") != "Bearer admin-secret":
            return self.respond(401, {})
        return self.respond(200, list(self.server.events.values()))


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), GatewayHandler)
        self.server.events = {}
        self.server.change_duplicate_id = False
        self.server.force_event_status = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.device_id = str(uuid.uuid4())

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def run_scenario(self, scenario, admin_token="admin-secret"):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {
            "ACCESS_GATEWAY_DEVICE_ID": self.device_id,
            "ACCESS_GATEWAY_DEVICE_KEY": "device-secret",
            "ACCESS_GATEWAY_ADMIN_TOKEN": admin_token,
        }), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = simulator.main(["--scenario", scenario, "--base-url", self.base_url])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_all_scenarios(self):
        for scenario, expected_count in (("valid", 1), ("duplicate", 1),
                                         ("invalid", 0), ("invalid-key", 0)):
            with self.subTest(scenario=scenario):
                self.server.events.clear()
                code, output, error = self.run_scenario(scenario)
                self.assertEqual(0, code, error)
                self.assertIn(f"Persisted records: {expected_count}", output)
                self.assertIn("[RESULT] PASS", output)
                self.assertEqual(expected_count, len(self.server.events))
                self.assertNotIn("device-secret", output + error)
                self.assertNotIn("admin-secret", output + error)

    def test_duplicate_with_different_id_fails(self):
        self.server.change_duplicate_id = True
        code, _, error = self.run_scenario("duplicate")
        self.assertEqual(1, code)
        self.assertIn("did not preserve the original event", error)

    def test_history_authentication_failure_fails(self):
        code, _, error = self.run_scenario("valid", admin_token="wrong-admin")
        self.assertEqual(1, code)
        self.assertIn("expected HTTP 200, received HTTP 401", error)

    def test_unexpected_event_status_fails(self):
        self.server.force_event_status = 500
        code, _, error = self.run_scenario("valid")
        self.assertEqual(1, code)
        self.assertIn("expected HTTP 201, received HTTP 500", error)

    def test_connection_failure_fails(self):
        with patch.object(simulator, "request_json", side_effect=simulator.SimulatorError("HTTP request failed")):
            code, _, error = self.run_scenario("valid")
        self.assertEqual(1, code)
        self.assertIn("HTTP request failed", error)


if __name__ == "__main__":
    unittest.main()
