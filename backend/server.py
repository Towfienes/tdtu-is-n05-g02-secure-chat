"""Loopback-only HTTPS message board for the Android demonstration."""

import argparse
import json
import ssl
import sys
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class ChatServer(HTTPServer):
    def __init__(self, address, handler):
        self.messages = []
        self.next_id = 1
        super().__init__(address, handler)

    def get_request(self):
        client, address = super().get_request()
        client.settimeout(5)
        return client, address

    def handle_error(self, request, client_address):
        error = sys.exception()
        if isinstance(error, ssl.SSLError):
            print(f"TLS connection closed: {error.reason}", flush=True)
        elif isinstance(error, (ConnectionError, TimeoutError)):
            print(f"Client connection closed: {type(error).__name__}", flush=True)
        else:
            super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *args):
        # Record method and outcome only. The demonstration never logs message bodies.
        print(f"HTTP {self.command} {args[1]}", flush=True)

    def log_error(self, _format, *_args):
        print("HTTP invalid request", flush=True)

    def do_GET(self):
        if self.path == "/messages":
            self.reply(200, self.server.messages)
        else:
            self.reply(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/messages":
            return self.reply(404, {"error": "not_found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4096:
                return self.reply(413, {"error": "body_too_large"})
            if length < 1:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise TypeError
            text = text.strip()
            if not 1 <= len(text) <= 280:
                raise ValueError
            text.encode(
                "utf-8"
            )  # Reject unpaired surrogates before mutating the conversation.
        except (TypeError, ValueError, TimeoutError):
            return self.reply(400, {"error": "invalid_message"})
        message = {"id": self.server.next_id, "text": text}
        self.server.next_id += 1
        self.server.messages.append(message)
        self.server.messages = self.server.messages[-30:]
        self.reply(201, self.server.messages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", choices=("a", "b", "backup", "untrusted"))
    parser.add_argument("--pki", type=Path, default=Path(".lab/pki"))
    args = parser.parse_args()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(
        args.pki / f"{args.fixture}.crt", args.pki / f"{args.fixture}.key"
    )
    with ChatServer(("127.0.0.1", 8443), Handler) as server:
        server.socket = context.wrap_socket(
            server.socket, server_side=True, do_handshake_on_connect=False
        )
        print(f"READY 127.0.0.1:8443 fixture={args.fixture}", flush=True)
        with suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
