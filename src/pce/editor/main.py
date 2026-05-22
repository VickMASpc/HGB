from __future__ import annotations

import argparse
from pathlib import Path

from pce.editor.app import EditorApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open the PointClick Engine editor.")
    parser.add_argument("--project", help="Optional project folder to open.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    EditorApp(Path(args.project) if args.project else None).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

