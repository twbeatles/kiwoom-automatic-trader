import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, Set, Tuple

from refactor_introspection import collect_inherited_methods, collect_signal_names, read_text, resolve_class


ROOT_DIR = Path(__file__).resolve().parent.parent
PRE_LARGE_SPLIT_PATH = ROOT_DIR / "docs/refactor/pre_large_split_manifest.json"
BASELINE_PATH = PRE_LARGE_SPLIT_PATH if PRE_LARGE_SPLIT_PATH.exists() else ROOT_DIR / "docs/refactor/baseline_manifest.json"
CANONICAL_WINDOW_PATH = ROOT_DIR / "app/core/window.py"
MAIN_WINDOW_PATH = ROOT_DIR / "app/main_window.py"
CLASS_NAME = "KiwoomProTrader"


def _collect_dict_literal_keys(func_node: ast.FunctionDef) -> Set[str]:
    keys: Set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _collect_settings_access_keys(func_node: ast.FunctionDef) -> Set[str]:
    keys: Set[str] = set()

    for node in ast.walk(func_node):
        if isinstance(node, ast.Compare) and any(isinstance(op, ast.In) for op in node.ops):
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                keys.add(node.left.value)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and isinstance(node.func.value, ast.Name) and node.func.value.id == "settings":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    keys.add(node.args[0].value)

        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "settings":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
    return keys


def _source_of_node(path: Path, node: ast.AST) -> str:
    lines = read_text(path).splitlines(keepends=True)
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", None)
    if start is None or end is None:
        raise RuntimeError("node is missing source location information")
    return "".join(lines[start - 1:end])


def _collect_refactored_state() -> Tuple[Set[str], Set[str], Dict[str, ast.FunctionDef], Dict[str, Path]]:
    source_path = CANONICAL_WINDOW_PATH if CANONICAL_WINDOW_PATH.exists() else MAIN_WINDOW_PATH
    methods, origins, _ = collect_inherited_methods(source_path, CLASS_NAME)
    _resolved_path, _mod, main_class = resolve_class(source_path, CLASS_NAME)
    return set(methods.keys()), collect_signal_names(main_class), methods, origins


def _collect_shortcut_keys(method_node: ast.FunctionDef, method_path: Path) -> Set[str]:
    source = _source_of_node(method_path, method_node)
    pattern = re.compile(r"Config\.SHORTCUTS\[['\"]([^'\"]+)['\"]\]")
    return {m.group(1) for m in pattern.finditer(source)}


def _print_diff(label: str, baseline: Set[str], current: Set[str], allow_added: bool = False) -> int:
    missing = sorted(baseline - current)
    added = sorted(current - baseline)
    if not missing and (allow_added or not added):
        print(f"[OK] {label}: parity")
        return 0
    print(f"[FAIL] {label}")
    if missing:
        print(f"  Missing ({len(missing)}): {missing}")
    if added and not allow_added:
        print(f"  Added ({len(added)}): {added}")
    elif added and allow_added:
        print(f"  Added ({len(added)}) allowed: {added}")
    return 1


def main() -> int:
    if not BASELINE_PATH.exists():
        print(f"[FAIL] Missing baseline: {BASELINE_PATH}")
        return 1
    if not MAIN_WINDOW_PATH.exists() and not CANONICAL_WINDOW_PATH.exists():
        print(f"[FAIL] Missing refactored class file: {CANONICAL_WINDOW_PATH} or {MAIN_WINDOW_PATH}")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    try:
        method_set, signal_set, methods, origins = _collect_refactored_state()
    except Exception as exc:
        print(f"[FAIL] Unable to parse refactored state: {exc}")
        return 1

    failures = 0
    failures += _print_diff("Method Set", set(baseline.get("methods", [])), method_set, allow_added=True)
    failures += _print_diff("Required Signals", set(baseline.get("required_signals", [])), signal_set)

    required_methods = [
        "_save_settings",
        "_load_settings",
        "_get_current_settings",
        "_apply_settings",
        "_setup_shortcuts",
    ]
    for method_name in required_methods:
        if method_name not in methods:
            print(f"[FAIL] Required method not found: {method_name}")
            failures += 1

    if failures:
        print(f"[FAIL] Verification failed early ({failures} checks)")
        return 1

    save_keys = _collect_dict_literal_keys(methods["_save_settings"])
    load_keys = _collect_settings_access_keys(methods["_load_settings"])
    profile_get_keys = _collect_dict_literal_keys(methods["_get_current_settings"])
    profile_apply_keys = _collect_settings_access_keys(methods["_apply_settings"])
    shortcut_keys = _collect_shortcut_keys(methods["_setup_shortcuts"], origins["_setup_shortcuts"])

    failures += _print_diff("_save_settings keys", set(baseline.get("save_settings_keys", [])), save_keys, allow_added=True)
    failures += _print_diff("_load_settings keys", set(baseline.get("load_settings_keys", [])), load_keys, allow_added=True)
    failures += _print_diff("_get_current_settings keys", set(baseline.get("profile_get_keys", [])), profile_get_keys, allow_added=True)
    failures += _print_diff("_apply_settings keys", set(baseline.get("profile_apply_keys", [])), profile_apply_keys, allow_added=True)
    failures += _print_diff("Shortcut Keys", set(baseline.get("shortcut_keys", [])), shortcut_keys)

    if failures:
        print(f"[FAIL] Verification failed ({failures} checks)")
        return 1

    print("[OK] Refactor verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
