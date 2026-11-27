#!/usr/bin/env python3
"""Exercise the Access Gateway device event API."""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


TIMEOUT_SECONDS = 10
STATUS_LABELS = {200: "DUPLICATE", 201: "CREATED", 400: "BAD REQUEST", 401: "UNAUTHORIZED"}


class SimulatorError(Exception):
    pass


def request_json(base_url, path, token, method="GET", payload=None):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = Request(base_url + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except HTTPError as error:
        try:
            return error.code, error.read()
        finally:
            error.close()
    except (URLError, TimeoutError, OSError) as error:
        raise SimulatorError(f"HTTP request failed: {error.reason if isinstance(error, URLError) else error}") from error


def parse_json(raw, description):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SimulatorError(f"{description} returned invalid JSON") from error


def expect_status(actual, expected):
    if actual != expected:
        raise SimulatorError(f"expected HTTP {expected}, received HTTP {actual}")


def config_from_environment(args):
    device_id = os.environ.get("ACCESS_GATEWAY_DEVICE_ID", "").strip()
    device_key = os.environ.get("ACCESS_GATEWAY_DEVICE_KEY", "").strip()
    admin_token = os.environ.get("ACCESS_GATEWAY_ADMIN_TOKEN", "").strip()
    credential_ref = os.environ.get("ACCESS_GATEWAY_CREDENTIAL_REF", "").strip()
    missing = [name for name, value in (
        ("ACCESS_GATEWAY_DEVICE_ID", device_id),
        ("ACCESS_GATEWAY_DEVICE_KEY", device_key),
        ("ACCESS_GATEWAY_ADMIN_TOKEN", admin_token),
        ("ACCESS_GATEWAY_CREDENTIAL_REF", credential_ref),
    ) if not value]
    if missing:
        raise SimulatorError("missing environment variable(s): " + ", ".join(missing))
    try:
        device_id = str(uuid.UUID(device_id))
    except ValueError as error:
        raise SimulatorError("ACCESS_GATEWAY_DEVICE_ID must be a UUID") from error

    base_url = args.base_url.rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        raise SimulatorError("--base-url must be an HTTP(S) origin, without a path or query")
    return base_url, device_id, device_key, admin_token, credential_ref


def run(args):
    base_url, device_id, device_key, admin_token, credential_ref = config_from_environment(args)
    external_id = "EVT-" + uuid.uuid4().hex.upper()
    event = {
        "deviceId": device_id,
        "externalEventId": external_id,
        "eventType": "ACCESS_GRANTED",
        "credentialRef": credential_ref,
        "occurredAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if args.scenario == "invalid":
        del event["occurredAt"]

    print(f"[SIMULATOR] Device: {device_id}")
    print()
    attempts = 2 if args.scenario == "duplicate" else 1
    first_response = None
    expected = {"valid": 201, "duplicate": 201, "invalid": 400, "invalid-key": 401}
    for attempt in range(1, attempts + 1):
        action = "Resending" if attempt == 2 else "Sending"
        print(f"[{attempt}] {action} event {external_id}")
        token = "invalid-" + uuid.uuid4().hex if args.scenario == "invalid-key" else device_key
        status, raw = request_json(base_url, "/device-events", token, "POST", event)
        expected_status = 200 if attempt == 2 else expected[args.scenario]
        print(f"    HTTP {status} - {STATUS_LABELS.get(status, 'UNEXPECTED')}")
        expect_status(status, expected_status)
        if status in (200, 201):
            response = parse_json(raw, "event ingestion")
            if not isinstance(response, dict) or not response.get("id"):
                raise SimulatorError("event ingestion response has no id")
            if response.get("externalEventId") != external_id or response.get("deviceId") != device_id:
                raise SimulatorError("event ingestion response identifies a different event or device")
            if attempt == 2 and (response["id"] != first_response["id"]
                                 or response.get("receivedAt") != first_response.get("receivedAt")):
                raise SimulatorError("duplicate response did not preserve the original event")
            first_response = response
        print()

    print(f"[{attempts + 1}] Querying event history")
    path = f"/devices/{quote(device_id)}/events?limit=100"
    history_status, raw = request_json(base_url, path, admin_token)
    expect_status(history_status, 200)
    history = parse_json(raw, "event history")
    if not isinstance(history, list):
        raise SimulatorError("event history response must be an array")
    matches = [item for item in history if isinstance(item, dict) and item.get("externalEventId") == external_id]
    print(f"    Persisted records: {len(matches)}")
    expected_count = 0 if args.scenario in ("invalid", "invalid-key") else 1
    if len(matches) != expected_count:
        raise SimulatorError(f"expected {expected_count} persisted record(s) for {external_id}")
    if expected_count and matches[0].get("id") != first_response["id"]:
        raise SimulatorError("event history contains a different persisted id")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("valid", "duplicate", "invalid", "invalid-key"), required=True)
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args(argv)
    try:
        run(args)
    except SimulatorError as error:
        print(f"\n[RESULT] FAIL - {error}", file=sys.stderr)
        return 1
    print("\n[RESULT] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
