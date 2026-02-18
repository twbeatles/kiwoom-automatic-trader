import ast
import json
import re
from pathlib import Path
from typing import Dict, Set, Tuple


CLASS_NAME = "KiwoomProTrader"
DEFAULT_SOURCE = "키움증권 자동매매.py"
DEFAULT_OUTPUT = "docs/refactor/baseline_manifest.json"
FALLBACK_SOURCE = "app/main_window.py"
REQUIRED_SIGNALS = [
    "sig_log",
    "sig_execution",
    "sig_order_execution",
    "sig_update_table",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _parse_source(path: Path) -> Tuple[ast.Module, ast.ClassDef, str]:
    source = _read_text(path)
    mod = ast.parse(source)

    class_node = None
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == CLASS_NAME:
            class_node = node
            break
    if class_node is None:
        raise RuntimeError(f"{CLASS_NAME} not found in {path}")

    return mod, class_node, source


def _collect_signal_names(class_node: ast.ClassDef) -> Set[str]:
    signals: Set[str] = set()
    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if isinstance(func, ast.Name) and func.id == "pyqtSignal":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    signals.add(target.id)
    return signals


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
        if isinstance(node, ast.Compare):
            if any(isinstance(op, ast.In) for op in node.ops):
                left = node.left
                if isinstance(left, ast.Constant) and isinstance(left.value, str):
                    keys.add(left.value)

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and isinstance(node.func.value, ast.Name) and node.func.value.id == "settings":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        keys.add(node.args[0].value)

        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == "settings":
                slc = node.slice
                if isinstance(slc, ast.Constant) and isinstance(slc.value, str):
                    keys.add(slc.value)
    return keys


def _collect_direct_methods(class_node: ast.ClassDef) -> Dict[str, ast.FunctionDef]:
    return {n.name: n for n in class_node.body if isinstance(n, ast.FunctionDef)}


def _collect_mixin_class_files(source_path: Path, mod: ast.Module) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    root = source_path.parent
    for node in mod.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 1:
            continue
        if not node.module or not node.module.startswith("mixins."):
            continue
        path = root / (node.module.replace(".", "/") + ".py")
        for alias in node.names:
            out[alias.name] = path
    return out


def _collect_all_methods(source_path: Path, mod: ast.Module, class_node: ast.ClassDef) -> Tuple[Dict[str, ast.FunctionDef], Dict[str, Path]]:
    methods: Dict[str, ast.FunctionDef] = {}
    method_origins: Dict[str, Path] = {}

    for name, node in _collect_direct_methods(class_node).items():
        methods[name] = node
        method_origins[name] = source_path

    mixin_files = _collect_mixin_class_files(source_path, mod)
    if not mixin_files:
        return methods, method_origins

    for base in class_node.bases:
        if not isinstance(base, ast.Name):
            continue
        base_name = base.id
        mixin_path = mixin_files.get(base_name)
        if mixin_path is None or not mixin_path.exists():
            continue

        mixin_mod = ast.parse(_read_text(mixin_path))
        mixin_class = None
        for n in mixin_mod.body:
            if isinstance(n, ast.ClassDef) and n.name == base_name:
                mixin_class = n
                break
        if mixin_class is None:
            continue

        for name, node in _collect_direct_methods(mixin_class).items():
            methods[name] = node
            method_origins[name] = mixin_path

    return methods, method_origins


def _collect_shortcuts(method_node: ast.FunctionDef, method_path: Path) -> Set[str]:
    lines = _read_text(method_path).splitlines(keepends=True)
    source = "".join(lines[method_node.lineno - 1:method_node.end_lineno])
    pattern = re.compile(r"Config\.SHORTCUTS\[['\"]([^'\"]+)['\"]\]")
    return {m.group(1) for m in pattern.finditer(source)}


def build_manifest(source_path: Path) -> Dict[str, object]:
    mod, class_node, _ = _parse_source(source_path)
    methods, method_origins = _collect_all_methods(source_path, mod, class_node)

    save_keys = _collect_dict_literal_keys(methods["_save_settings"]) if "_save_settings" in methods else set()
    load_keys = _collect_settings_access_keys(methods["_load_settings"]) if "_load_settings" in methods else set()
    profile_get_keys = _collect_dict_literal_keys(methods["_get_current_settings"]) if "_get_current_settings" in methods else set()
    profile_apply_keys = _collect_settings_access_keys(methods["_apply_settings"]) if "_apply_settings" in methods else set()

    shortcut_keys: Set[str] = set()
    if "_setup_shortcuts" in methods:
        shortcut_keys = _collect_shortcuts(methods["_setup_shortcuts"], method_origins["_setup_shortcuts"])

    method_names = sorted(methods.keys())

    manifest: Dict[str, object] = {
        "class_name": CLASS_NAME,
        "source": str(source_path),
        "method_count": len(method_names),
        "methods": method_names,
        "signals": sorted(_collect_signal_names(class_node)),
        "required_signals": REQUIRED_SIGNALS,
        "save_settings_keys": sorted(save_keys),
        "load_settings_keys": sorted(load_keys),
        "profile_get_keys": sorted(profile_get_keys),
        "profile_apply_keys": sorted(profile_apply_keys),
        "shortcut_keys": sorted(shortcut_keys),
    }
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build baseline manifest for refactor parity checks.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Source file containing KiwoomProTrader")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists() and Path(FALLBACK_SOURCE).exists():
        source_path = Path(FALLBACK_SOURCE)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        manifest = build_manifest(source_path)
    except RuntimeError:
        if source_path != Path(FALLBACK_SOURCE) and Path(FALLBACK_SOURCE).exists():
            source_path = Path(FALLBACK_SOURCE)
            manifest = build_manifest(source_path)
        else:
            raise

    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Manifest written: {output_path}")
    print(f"  Methods: {manifest['method_count']}")
    print(f"  Signals: {', '.join(manifest['signals'])}")


if __name__ == "__main__":
    main()
