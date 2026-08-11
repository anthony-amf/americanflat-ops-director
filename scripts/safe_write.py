#!/usr/bin/env python3
"""
Write a file only when doing so cannot destroy someone else's work.

Standing rule in this repo: nothing deletes or destructively overwrites. But
these scripts do have to rewrite their own output — the dashboard gets rebuilt
every week to the same filename, and that is the intended workflow.

The line between the two is authorship. A file this script wrote before is fair
game to replace; anything else is not. Every generated file carries a marker
near the top, and a write to an existing path is refused unless the marker is
there. So a mistyped filename fails loudly instead of quietly taking out a real
file.
"""

import sys
from pathlib import Path


def safe_write_text(path: Path, content: str, marker: str, what: str = "file") -> None:
    """Write content to path, refusing to overwrite a file we did not generate."""
    path = Path(path).expanduser()

    if path.exists():
        if path.is_dir():
            sys.exit(f"Refusing to write: {path} is a folder, not a {what}.")
        try:
            existing = path.read_text(errors="replace")
        except OSError as exc:
            sys.exit(f"Refusing to write: cannot read the existing {path} to check it ({exc}).")
        if marker not in existing:
            sys.exit(
                f"Refusing to overwrite {path} — it exists and was not written by this script.\n"
                f"Nothing has been changed. Either pick a different --out name, or move that file\n"
                f"somewhere else yourself first if you really do want it replaced."
            )

    if marker not in content:
        # A generated file without its own marker could never be rewritten.
        raise ValueError(f"generated {what} is missing its marker {marker!r}")

    path.write_text(content)
