import ast
from pathlib import Path
from typing import Dict, Optional, Set, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse(path: Path) -> ast.Module:
    return ast.parse(read_text(path))


def find_class(mod: ast.Module, class_name: str) -> Optional[ast.ClassDef]:
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def collect_methods(class_node: ast.ClassDef) -> Dict[str, ast.FunctionDef]:
    return {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}


def collect_signal_names(class_node: ast.ClassDef) -> Set[str]:
    signals: Set[str] = set()
    for node in class_node.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if isinstance(func, ast.Name) and func.id == "pyqtSignal":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    signals.add(target.id)
    return signals


def _module_name_for_path(path: Path) -> str:
    relative = path.resolve().relative_to(ROOT_DIR)
    if relative.name == "__init__.py":
        relative = relative.parent
    else:
        relative = relative.with_suffix("")
    return ".".join(relative.parts)


def _resolve_import_module(source_path: Path, module: str | None, level: int) -> str:
    if level == 0:
        return module or ""

    current_module = _module_name_for_path(source_path)
    current_parts = current_module.split(".")
    package_parts = current_parts if source_path.name == "__init__.py" else current_parts[:-1]
    keep = max(0, len(package_parts) - (level - 1))
    parts = package_parts[:keep]
    if module:
        parts.extend(module.split("."))
    return ".".join(part for part in parts if part)


def _module_to_path(module_name: str) -> Optional[Path]:
    if not module_name:
        return None
    module_path = ROOT_DIR / (module_name.replace(".", "/") + ".py")
    if module_path.exists():
        return module_path
    package_path = ROOT_DIR / module_name.replace(".", "/") / "__init__.py"
    if package_path.exists():
        return package_path
    return None


def _import_map(source_path: Path, mod: ast.Module) -> Dict[str, Tuple[Path, str]]:
    mapping: Dict[str, Tuple[Path, str]] = {}
    for node in mod.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        module_name = _resolve_import_module(source_path, node.module, node.level)
        module_path = _module_to_path(module_name)
        if module_path is None:
            continue
        for alias in node.names:
            local_name = alias.asname or alias.name
            mapping[local_name] = (module_path, alias.name)
    return mapping


def resolve_class(
    path: Path,
    class_name: str,
    seen: Set[Tuple[Path, str]] | None = None,
) -> Tuple[Path, ast.Module, ast.ClassDef]:
    seen = seen or set()
    key = (path.resolve(), class_name)
    if key in seen:
        raise RuntimeError(f"cyclic class import while resolving {class_name} from {path}")
    seen.add(key)

    mod = parse(path)
    class_node = find_class(mod, class_name)
    if class_node is not None:
        return path, mod, class_node

    imported = _import_map(path, mod).get(class_name)
    if imported is None:
        raise RuntimeError(f"{class_name} not found in {path}")
    imported_path, imported_name = imported
    return resolve_class(imported_path, imported_name, seen)


def collect_inherited_methods(
    path: Path,
    class_name: str,
) -> Tuple[Dict[str, ast.FunctionDef], Dict[str, Path], ast.ClassDef]:
    methods: Dict[str, ast.FunctionDef] = {}
    origins: Dict[str, Path] = {}

    def visit(current_path: Path, current_name: str, seen: Set[Tuple[Path, str]]) -> ast.ClassDef:
        resolved_path, mod, class_node = resolve_class(current_path, current_name, seen)

        for name, node in collect_methods(class_node).items():
            methods.setdefault(name, node)
            origins.setdefault(name, resolved_path)

        imports = _import_map(resolved_path, mod)
        local_classes = {
            node.name: node
            for node in mod.body
            if isinstance(node, ast.ClassDef)
        }
        for base in class_node.bases:
            if not isinstance(base, ast.Name):
                continue
            imported = imports.get(base.id)
            if imported is not None:
                base_path, imported_name = imported
                try:
                    visit(base_path, imported_name, set(seen))
                except RuntimeError:
                    continue
            elif base.id in local_classes:
                for name, node in collect_methods(local_classes[base.id]).items():
                    methods.setdefault(name, node)
                    origins.setdefault(name, resolved_path)
        return class_node

    root_class = visit(path, class_name, set())
    return methods, origins, root_class
