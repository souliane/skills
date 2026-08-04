"""Import an acroform script without the real pikepdf wheel.

The scripts import pikepdf at module level, but the repo's dev group deliberately
carries no PDF stack — these tests exercise the pure logic around it.
"""

import importlib
import sys
from types import ModuleType


def import_with_pikepdf_stub(module_name: str) -> ModuleType:
    sys.modules.pop(module_name, None)
    stub = ModuleType("pikepdf")
    stub.__dict__.update(
        {
            "Array": list,
            "Dictionary": dict,
            "Page": object,
            "Pdf": object,
            "Stream": object,
        }
    )
    sys.modules["pikepdf"] = stub
    return importlib.import_module(module_name)
