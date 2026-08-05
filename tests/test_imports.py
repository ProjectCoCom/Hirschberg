"""
Summary: Python logic module 'Test Imports'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Test Imports'.

How it fits in: Imported and utilized by surrounding backend structures.
"""


from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path


def test_import_all_modules():
    """Walks through all modules in src/ and imports them to ensure there are no module-level import errors."""
    src_dir = Path(__file__).parent.parent / "src"

    # 1. Pre-import the global third-party mcp package with sys.path filtered
    # to ensure sys.modules['mcp'] is cached as the correct global package.
    orig_sys_path = list(sys.path)
    filtered_path = [p for p in sys.path if not (p.endswith("/src") or p.endswith("/src/") or p == "src")]

    sys.path = filtered_path
    sys.modules.pop("mcp", None)
    sys.modules.pop("mcp.server", None)
    sys.modules.pop("mcp.server.fastmcp", None)

    try:
        import mcp  # noqa: F401
        import mcp.server.fastmcp  # noqa: F401
    except Exception:
        pass
    finally:
        sys.path = orig_sys_path

    failed_modules = []
    # Discover all modules under src_dir
    for finder, name, ispkg in pkgutil.walk_packages([str(src_dir)]):
        # Determine the file path on disk to filter out namespace package merging pollution
        parts = name.split(".")
        path_as_dir = src_dir / "/".join(parts) / "__init__.py"
        path_as_file = src_dir / ("/".join(parts) + ".py")

        if not (path_as_dir.exists() or path_as_file.exists()):
            # This is namespace pollution from the global mcp package, ignore it
            continue

        module_to_import = f"src.{name}"
        try:
            importlib.import_module(module_to_import)
        except Exception as e:
            failed_modules.append((module_to_import, str(e)))

    if failed_modules:
        msg = "\n".join([f"Module '{name}' failed to import: {err}" for name, err in failed_modules])
        raise ImportError(f"Failed to import some modules under src/:\n{msg}")
