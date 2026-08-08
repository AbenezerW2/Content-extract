#!/usr/bin/env python3
"""Launch the unified Content Extract desktop application."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DESKTOP_DIR = ROOT_DIR / "apps" / "web-extractor"
DESKTOP_APP = DESKTOP_DIR / "app.py"


def main() -> None:
    sys.path.insert(0, str(DESKTOP_DIR))
    os.environ["CONTENT_EXTRACT_ROOT"] = str(ROOT_DIR)
    os.chdir(DESKTOP_DIR)
    runpy.run_path(str(DESKTOP_APP), run_name="__main__")


if __name__ == "__main__":
    main()
