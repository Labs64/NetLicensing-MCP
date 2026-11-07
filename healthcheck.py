"""Container health probe: GET /health in HTTP mode, always healthy in stdio mode."""

import os
import sys
import urllib.request


def _http_mode() -> bool:
    if os.getenv("MCP_TRANSPORT", "").lower() == "http":
        return True
    try:
        with open("/proc/1/cmdline", "rb") as f:
            return b"http" in f.read().split(b"\0")
    except OSError:
        return False


def main() -> int:
    if not _http_mode():
        return 0
    port = os.getenv("MCP_PORT", "8000")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as r:  # noqa: S310
            return 0 if r.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
