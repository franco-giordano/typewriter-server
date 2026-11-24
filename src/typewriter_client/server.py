import argparse
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4

from typewriter_client.events import Event, validate_text


class EventServer(HTTPServer):
    latest: Event | None = None


class EventHandler(BaseHTTPRequestHandler):
    server: EventServer
    timeout = 5

    def do_GET(self) -> None:
        if self.path != "/events":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "expected /events"})
            return

        latest = self.server.latest
        self.send_json(HTTPStatus.OK, {"events": [asdict(latest)] if latest else []})

    def do_POST(self) -> None:
        if self.path != "/events":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "expected /events"})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "expected application/json"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("expected a JSON request body")
            if length > 65_536:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request exceeds 64 KiB"})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("expected a JSON object with a text field")
            text = validate_text(payload.get("text"))
        except ValueError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        event = Event(id=str(uuid4()), text=text)
        self.server.latest = event
        self.send_json(HTTPStatus.CREATED, asdict(event))

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code="-", size="-") -> None:
        if self.command != "GET" or code != HTTPStatus.OK:
            super().log_request(code, size)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve an in-memory typed-text event feed.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5678, help="Bind port (default: 5678)")
    args = parser.parse_args()

    try:
        with EventServer((args.host, args.port), EventHandler) as server:
            host, port = server.server_address
            print(f"Serving GET and POST at http://{host}:{port}/events", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        parser.exit(1, f"Could not start the event server: {exc}\n")
