"""Make ac-django rule scripts importable for tests."""

import sys
from pathlib import Path

_rules_dir = Path(__file__).resolve().parents[2] / "ac-django" / "rules"
if str(_rules_dir) not in sys.path:
    sys.path.insert(0, str(_rules_dir))
