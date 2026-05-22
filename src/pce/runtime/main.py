from __future__ import annotations

import argparse
from pathlib import Path

from pce.runtime.app import PygameApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a PointClick Engine project.")
    parser.add_argument("--project", required=True, help="Path to a portable project folder.")
    parser.add_argument("--scene", help="Optional scene id to start from.")
    parser.add_argument("--slot", help="Optional named save slot to load.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = PygameApp(Path(args.project), args.scene, args.slot)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

