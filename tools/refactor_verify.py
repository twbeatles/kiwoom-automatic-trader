import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT_DIR / "docs/refactor/baseline_manifest.json"
MAIN_WINDOW_PATH = ROOT_DIR / "app/main_window.py"
CLASS_NAME = "KiwoomProTrader"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _parse(path: Path) -> ast.Module:
    return ast.parse(_read(path))


def _find_class(mod: ast.Module, class_name: str) -> ast.ClassDef:
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise RuntimeError(f"{class_name} not found in {mod}")


def _collect_methods(class_node: ast.ClassDef) -> Dict[str, ast.FunctionDef]:
    return {n.name: n for n in class_node.body if isinstance(n, ast.FunctionDef)}


def _collect_signal_names(class_node: ast.ClassDef) -> Set[str]:
    out: Set[str] = set()
    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if isinstance(node.value.func, ast.Name) and node.value.func.id == "pyqtSignal":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.add(target.id)
    return out


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
    lines = _read(path).splitlines(keepends=True)
    return "".join(lines[node.lineno - 1:node.end_lineno])


def _collect_mixin_class_files(main_mod: ast.Module) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for node in main_mod.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 1:
            continue
        if not node.module or not node.module.startswith("mixins."):
            continue
        path = ROOT_DIR / "app" / (node.module.replace(".", "/") + ".py")
        for alias in node.names:
            out[alias.name] = path
    return out


def _collect_refactored_state() -> Tuple[Set[str], Set[str], Dict[str, ast.FunctionDef], Dict[str, Path]]:
    main_mod = _parse(MAIN_WINDOW_PATH)
    main_class = _find_class(main_mod, CLASS_NAME)
    mixin_files = _collect_mixin_class_files(main_mod)

    all_methods: Dict[str, ast.FunctionDef] = {}
    method_origin: Dict[str, Path] = {}

    # methods defined directly in main class
    for name, node in _collect_methods(main_class).items():
        all_methods[name] = node
        method_origin[name] = MAIN_WINDOW_PATH

    # methods inherited from mixins
    for base in main_class.bases:
        if not isinstance(base, ast.Name):
            continue
        base_name = base.id
        if base_name not in mixin_files:
            continue
        mixin_path = mixin_files[base_name]
        mixin_mod = _parse(mixin_path)
        mixin_class = _find_class(mixin_mod, base_name)
        for name, node in _collect_methods(mixin_class).items():
            all_methods[name] = node
            method_origin[name] = mixin_path

    return set(all_methods.keys()), _collect_signal_names(main_class), all_methods, method_origin


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
    if not MAIN_WINDOW_PATH.exists():
        print(f"[FAIL] Missing refactored class file: {MAIN_WINDOW_PATH}")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    try:
        method_set, signal_set, methods, origins = _collect_refactored_state()
    except Exception as exc:
        print(f"[FAIL] Unable to parse refactored state: {exc}")
        return 1

    failures = 0
    failures += _print_diff("Method Set", set(baseline.get("methods", [])), method_set)
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
