from __future__ import annotations

import argparse

from . import server


def run() -> None:
    parser = argparse.ArgumentParser(description="MindState MCP server")
    parser.parse_args()
    server.start()
