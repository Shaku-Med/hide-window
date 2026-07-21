#!/usr/bin/env python3
"""Local web server that probes every common way a page can detect you left."""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8765


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory or HERE, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Focus / visibility detection probe")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    handler = functools.partial(QuietHandler, directory=HERE)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Focus probe running at {url}")
        print("Open that URL in the browser you want to test.")
        print("In Cloak: select that browser window -> Keep selected active,")
        print("then hide another window and click around. Watch the probe.")
        print("Press Ctrl+C to stop.")
        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
