import importlib
import site
import sys
import sysconfig
from pathlib import Path

import hou

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
    ignore_paths = set()
    ignore_paths.add(Path(sysconfig.get_paths()["stdlib"]).resolve())

    if hfs_path := hou.getenv("HFS"):
        ignore_paths.add(Path(hfs_path).expanduser().resolve())

    # try:
    #     for site_pkg in site.getsitepackages():
    #         ignore_paths.add(Path(site_pkg).resolve())
    #     ignore_paths.add(Path(site.getusersitepackages()).resolve())
    # except AttributeError:
    #     pass  # Fallback for non-standard python builds

    reloads = set()
    with hou.undos.disabler():  # pyright: ignore[reportGeneralTypeIssues]
        for module_name, module in list(sys.modules.items()):
            if module_name == "__main__":
                continue

            if not module or not hasattr(module, "__file__") or not module.__file__:
                continue

            try:
                module_file = Path(module.__file__).resolve()
            except OSError:
                continue

            if module_file.suffix.lower() in compiled_suffixes:
                continue

            if any(
                check_child_path(module_file, ignore_dir) for ignore_dir in ignore_paths
            ):
                continue

            try:
                importlib.reload(module)
                reloads.add(module.__name__)
            except (AttributeError, ModuleNotFoundError):
                continue
