from __future__ import annotations

import importlib
import sys
import sysconfig
from pathlib import Path
from typing import Optional

import hou
from houtils.utils.ui import background_notify

compiled_suffixes = (".so", ".pyd", ".dll", ".dylib")


def check_child_path(child: Path, parent: Path) -> bool:
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()

        try:
            return child_resolved.is_relative_to(parent_resolved)
        except AttributeError:
            try:
                child_resolved.relative_to(parent_resolved)
                return True
            except (ValueError, OSError):
                return False

    except (ValueError, OSError):
        return False


def main():
    with hou.undos.disabler():
        # Get standard library path
        stdlib_dir = Path(sysconfig.get_paths()["stdlib"]).resolve()

        # Get Houdini installation path to ignore
        ignore_path: Optional[Path] = None
        if hh_path := hou.getenv("HH"):
            ignore_path = Path(hh_path).expanduser().resolve()

        # Iterate over a snapshot of module names
        for mod_name in list(sys.modules.keys()):
            if mod_name == "__main__":
                continue

            module = sys.modules.get(mod_name)
            if not module or not hasattr(module, "__file__") or not module.__file__:
                continue

            try:
                module_file = Path(module.__file__).resolve()
            except OSError:
                continue

            # Skip compiled extensions
            if module_file.suffix.lower() in compiled_suffixes:
                continue

            # Skip standard library
            if check_child_path(module_file, stdlib_dir):
                continue

            # Skip Houdini installation directory
            if ignore_path and check_child_path(module_file, ignore_path):
                continue

            # Attempt reload
            try:
                importlib.reload(module)
                modules_reloaded = True
            except (ImportError, SyntaxError, AttributeError, TypeError) as e:
                # print(f"ERROR: Couldn't reload {mod_name}: {e}")
                pass
