"""OBus Relay Pad: a local push-to-talk microphone client for a paired PC."""

from __future__ import annotations

import argparse
import functools
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


CLIENT_DIR = Path(__file__).with_name("relay_pad")


def serve(port: int) -> None:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(CLIENT_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"OBus Relay Pad is running at {url}")
    threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the OBus Relay Pad microphone client.")
    parser.add_argument("--port", type=int, default=8123)
    serve(parser.parse_args().port)
