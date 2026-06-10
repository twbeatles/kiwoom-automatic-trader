import ast
import json
import re
from pathlib import Path
from typing import Dict, Set

from refactor_introspection import (
    collect_inherited_methods,
    collect_signal_names,
    read_text,
    resolve_class,
)


CLASS_NAME = "KiwoomProTrader"
DEFAULT_SOURCE = "키움증권 자동매매.py"
DEFAULT_OUTPUT = "docs/refactor/baseline_manifest.json"
FALLBACK_SOURCES = ["app/core/window.py", "app/main_window.py"]
REQUIRED_SIGNALS = [
    "sig_log",
    "sig_execution",
    "sig_order_execution",
    "sig_update_table",
]


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


def _collect_shortcuts(method_node: ast.FunctionDef, method_path: Path) -> Set[str]:
    lines = read_text(method_path).splitlines(keepends=True)
    source = "".join(lines[method_node.lineno - 1:method_node.end_lineno])
    pattern = re.compile(r"Config\.SHORTCUTS\[['\"]([^'\"]+)['\"]\]")
    return {m.group(1) for m in pattern.finditer(source)}


def _resolve_source_path(source: str) -> Path:
    source_path = Path(source)
    candidates = [source_path] if source_path.exists() else []
    candidates.extend(Path(fallback) for fallback in FALLBACK_SOURCES if Path(fallback).exists())
    for candidate in candidates:
        try:
            resolve_class(candidate, CLASS_NAME)
            return candidate
        except RuntimeError:
            continue
    raise RuntimeError(f"{CLASS_NAME} not found in {source} or fallbacks")


def build_manifest(source_path: Path) -> Dict[str, object]:
    resolved_path, _mod, class_node = resolve_class(source_path, CLASS_NAME)
    methods, method_origins, _ = collect_inherited_methods(source_path, CLASS_NAME)

    save_keys = _collect_dict_literal_keys(methods["_save_settings"]) if "_save_settings" in methods else set()
    load_keys = _collect_settings_access_keys(methods["_load_settings"]) if "_load_settings" in methods else set()
    profile_get_keys = _collect_dict_literal_keys(methods["_get_current_settings"]) if "_get_current_settings" in methods else set()
    profile_apply_keys = _collect_settings_access_keys(methods["_apply_settings"]) if "_apply_settings" in methods else set()

    shortcut_keys: Set[str] = set()
    if "_setup_shortcuts" in methods:
        shortcut_keys = _collect_shortcuts(methods["_setup_shortcuts"], method_origins["_setup_shortcuts"])

    method_names = sorted(methods.keys())

    return {
        "class_name": CLASS_NAME,
        "source": str(resolved_path),
        "method_count": len(method_names),
        "methods": method_names,
        "signals": sorted(collect_signal_names(class_node)),
        "required_signals": REQUIRED_SIGNALS,
        "save_settings_keys": sorted(save_keys),
        "load_settings_keys": sorted(load_keys),
        "profile_get_keys": sorted(profile_get_keys),
        "profile_apply_keys": sorted(profile_apply_keys),
        "shortcut_keys": sorted(shortcut_keys),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build baseline manifest for refactor parity checks.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Source file containing KiwoomProTrader")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(source_path)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_signals = manifest.get("signals", [])
    signals = [str(signal) for signal in raw_signals] if isinstance(raw_signals, list) else []
    print(f"[OK] Manifest written: {output_path}")
    print(f"  Methods: {manifest['method_count']}")
    print(f"  Signals: {', '.join(signals)}")


if __name__ == "__main__":
    main()
