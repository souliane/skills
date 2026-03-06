"""Make ac-editing-acroforms scripts importable for tests."""

import sys
from pathlib import Path

# Add the scripts directory to sys.path so `import golden_diff` works
_scripts_dir = Path(__file__).resolve().parents[2] / "ac-editing-acroforms" / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
