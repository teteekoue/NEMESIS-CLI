#!/usr/bin/env python3
"""Professional command-line launcher for NEMESIS.

The interactive experience remains implemented by :mod:`agent`; this module
only provides a stable, documented entry point and keeps the NEMAPI
server-side conversation model unchanged.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Sequence

VERSION = "2.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nemesis-cli",
        description="NEMESIS — controlled coding agent backed by NemApi.",
    )
    parser.add_argument("--debug", action="store_true", help="show agent diagnostic messages")
    parser.add_argument("--workspace", metavar="PATH", help="workspace used by all local tools")
    parser.add_argument("--config-dir", metavar="PATH", help="directory containing NEMESIS configuration")
    parser.add_argument("--version", action="version", version="NEMESIS-CLI {0}".format(VERSION))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.workspace:
        os.environ["NEMESIS_WORKSPACE"] = str(Path(args.workspace).expanduser().resolve())
    if args.config_dir:
        os.environ["NEMESIS_CONFIG_DIR"] = str(Path(args.config_dir).expanduser().resolve())
    # Import after environment configuration: paths.py derives its locations
    # at import time, so importing earlier would ignore CLI options.
    from agent import main as run_agent
    return run_agent(["--debug"] if args.debug else [])


if __name__ == "__main__":
    raise SystemExit(main())
