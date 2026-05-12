import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE_DIR = ROOT / ".hermes" / "team" / "control_plane"
FRAMEWORK_NAME = "\u8c03\u5ea6\u6846\u67b6"
FRAMEWORK_DIR = ROOT / ".hermes" / "team" / FRAMEWORK_NAME / "core"
CLI_DIR = ROOT / ".hermes" / "team" / FRAMEWORK_NAME / "cli"


def load_control_plane_module(name: str):
    control_plane_root = str(CONTROL_PLANE_DIR)
    if control_plane_root not in sys.path:
        sys.path.insert(0, control_plane_root)

    file_path = CONTROL_PLANE_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"control_plane_{name}", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_framework_module(name: str):
    file_path = FRAMEWORK_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"framework_{name}", file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_cli_module(file_name: str, alias: str):
    framework_root = str(FRAMEWORK_DIR.parent)
    if framework_root not in sys.path:
        sys.path.insert(0, framework_root)

    file_path = CLI_DIR / file_name
    spec = importlib.util.spec_from_file_location(alias, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

