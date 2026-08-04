"""Make ac-adopting-ruff scripts importable for tests."""

import sys
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parents[2] / "ac-adopting-ruff" / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
