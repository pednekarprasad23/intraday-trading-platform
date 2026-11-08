#!/usr/bin/env python3
"""Lightweight AST-based code graph and dependency analyzer for intraday-trading-platform.

Standard library only — zero external dependencies.
"""

import argparse
import ast
import json
from collections import defaultdict
from pathlib import Path


class CodeGraphVisitor(ast.NodeVisitor):
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.imports = []
        self.classes = []
        self.functions = []
        self.calls = []
        self.current_scope = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({"name": alias.name, "asname": alias.asname, "type": "import"})
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports.append({
                "module": module,
                "name": alias.name,
                "asname": alias.asname,
                "type": "from"
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))

        class_info = {
            "name": node.name,
            "lineno": node.lineno,
            "bases": bases,
            "methods": []
        }

        old_scope = list(self.current_scope)
        self.current_scope.append(node.name)

        for body_item in node.body:
            if isinstance(body_item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_info["methods"].append(body_item.name)

        self.classes.append(class_info)
        self.generic_visit(node)
        self.current_scope = old_scope

    def visit_FunctionDef(self, node):
        self._handle_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        self._handle_func(node, is_async=True)

    def _handle_func(self, node, is_async):
        scope_prefix = ".".join(self.current_scope)
        full_name = f"{scope_prefix}.{node.name}" if scope_prefix else node.name

        func_calls = []
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                func_name = ""
                if isinstance(subnode.func, ast.Name):
                    func_name = subnode.func.id
                elif isinstance(subnode.func, ast.Attribute):
                    func_name = ast.unparse(subnode.func)
                if func_name:
                    func_calls.append(func_name)
                    self.calls.append({
                        "caller": full_name,
                        "called": func_name,
                        "lineno": subnode.lineno
                    })

        self.functions.append({
            "name": node.name,
            "full_name": full_name,
            "lineno": node.lineno,
            "async": is_async,
            "calls": list(set(func_calls))
        })

        old_scope = list(self.current_scope)
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope = old_scope


def analyze_codebase(root_dir: Path):
    modules = {}
    symbol_map = defaultdict(list)
    call_graph = defaultdict(set)
    reverse_call_graph = defaultdict(set)
    import_graph = defaultdict(set)
    reverse_import_graph = defaultdict(set)

    py_files = sorted(list(root_dir.rglob("*.py")))

    for file_path in py_files:
        if ".venv" in file_path.parts or "venv" in file_path.parts or "__pycache__" in file_path.parts:
            continue

        rel_path = file_path.relative_to(root_dir.parent)
        # derive module name e.g. app.instruments.mappings
        parts = file_path.relative_to(root_dir).with_suffix("").parts
        module_name = "app." + ".".join(parts) if parts else "app"
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            continue

        visitor = CodeGraphVisitor(module_name)
        visitor.visit(tree)

        modules[module_name] = {
            "file_path": str(rel_path),
            "imports": visitor.imports,
            "classes": visitor.classes,
            "functions": visitor.functions,
            "calls": visitor.calls
        }

        # Record imports and module dependencies
        for imp in visitor.imports:
            imp_mod = imp.get("module") or imp.get("name")
            if imp_mod:
                import_graph[module_name].add(imp_mod)
                reverse_import_graph[imp_mod].add(module_name)

        # Record symbols
        for cls in visitor.classes:
            symbol_map[cls["name"]].append({
                "type": "class",
                "module": module_name,
                "file": str(rel_path),
                "lineno": cls["lineno"],
                "bases": cls["bases"],
                "methods": cls["methods"]
            })
        for fn in visitor.functions:
            symbol_map[fn["name"]].append({
                "type": "function",
                "module": module_name,
                "file": str(rel_path),
                "lineno": fn["lineno"],
                "async": fn["async"]
            })

        # Record calls
        for call in visitor.calls:
            caller = f"{module_name}.{call['caller']}"
            called = call["called"]
            call_graph[caller].add(called)
            reverse_call_graph[called].add(caller)

    return {
        "modules": modules,
        "symbol_map": {k: v for k, v in symbol_map.items()},
        "import_graph": {k: list(v) for k, v in import_graph.items()},
        "reverse_import_graph": {k: list(v) for k, v in reverse_import_graph.items()},
        "call_graph": {k: list(v) for k, v in call_graph.items()},
        "reverse_call_graph": {k: list(v) for k, v in reverse_call_graph.items()}
    }


def detect_hotspots(data):
    modules = data["modules"]
    import_graph = data["import_graph"]
    reverse_import_graph = data["reverse_import_graph"]
    symbol_map = data["symbol_map"]

    # In-degree (imported by how many modules)
    incoming_counts = {mod: len(rev) for mod, rev in reverse_import_graph.items()}
    # Out-degree (imports how many modules)
    outgoing_counts = {mod: len(deps) for mod, deps in import_graph.items()}

    sorted_incoming = sorted(incoming_counts.items(), key=lambda x: x[1], reverse=True)
    sorted_outgoing = sorted(outgoing_counts.items(), key=lambda x: x[1], reverse=True)

    # Trading domain key terms check
    domain_hotspots = {
        "kill_switch": [],
        "authentication": [],
        "instruments": [],
        "backtesting": [],
        "database_models": []
    }

    for mod_name, mod_info in modules.items():
        for cls in mod_info["classes"]:
            name_lower = cls["name"].lower()
            if any(k in name_lower for k in ["kill", "switch", "risk", "halt"]):
                domain_hotspots["kill_switch"].append({"symbol": cls["name"], "module": mod_name})
            if any(k in name_lower for k in ["user", "auth", "credential"]):
                domain_hotspots["authentication"].append({"symbol": cls["name"], "module": mod_name})
            if any(k in name_lower for k in ["instrument", "spec", "mapping"]):
                domain_hotspots["instruments"].append({"symbol": cls["name"], "module": mod_name})
            if any(k in name_lower for k in ["backtest", "walk", "simulation"]):
                domain_hotspots["backtesting"].append({"symbol": cls["name"], "module": mod_name})
        for fn in mod_info["functions"]:
            name_lower = fn["name"].lower()
            if any(k in name_lower for k in ["kill", "switch", "risk", "halt"]):
                domain_hotspots["kill_switch"].append({"symbol": fn["name"], "module": mod_name})
            if any(k in name_lower for k in ["auth", "login", "user"]):
                domain_hotspots["authentication"].append({"symbol": fn["name"], "module": mod_name})
            if any(k in name_lower for k in ["backtest", "run", "simulation"]):
                domain_hotspots["backtesting"].append({"symbol": fn["name"], "module": mod_name})

    return {
        "most_imported": sorted_incoming[:10],
        "most_dependent": sorted_outgoing[:10],
        "domain_hotspots": domain_hotspots
    }


def cmd_build(args):
    app_dir = Path("apps/api/app")
    if not app_dir.exists():
        print(f"Error: {app_dir} not found.")
        return

    print("Building code graph from apps/api/app/...")
    data = analyze_codebase(app_dir)
    hotspots = detect_hotspots(data)

    out_dir = Path(".graphify")
    out_dir.mkdir(exist_ok=True)

    # Write JSON files
    (out_dir / "modules.json").write_text(json.dumps(data["modules"], indent=2), encoding="utf-8")
    (out_dir / "symbols.json").write_text(json.dumps(data["symbol_map"], indent=2), encoding="utf-8")
    (out_dir / "dependencies.json").write_text(json.dumps({
        "import_graph": data["import_graph"],
        "reverse_import_graph": data["reverse_import_graph"]
    }, indent=2), encoding="utf-8")

    # Write dependency-map.md
    md_lines = ["# Code Graph Dependency Map\n", "## Modules & Files\n"]
    for mod_name, mod_info in data["modules"].items():
        md_lines.append(f"- **{mod_name}** (`{mod_info['file_path']}`)")
        if mod_info['classes']:
            classes_str = ", ".join(c['name'] for c in mod_info['classes'])
            md_lines.append(f"  - Classes: {classes_str}")
        if mod_info['functions']:
            funcs_str = ", ".join(f['name'] for f in mod_info['functions'][:10])
            md_lines.append(f"  - Functions: {funcs_str}")
    (out_dir / "dependency-map.md").write_text("\n".join(md_lines), encoding="utf-8")

    # Write hotspots.md
    hot_lines = ["# Architectural Hotspots & Trading Domain Index\n"]
    hot_lines.append("## Most Imported Modules\n")
    for mod, count in hotspots["most_imported"]:
        hot_lines.append(f"- `{mod}` ({count} incoming imports)")

    hot_lines.append("\n## Modules with Most Dependencies\n")
    for mod, count in hotspots["most_dependent"]:
        hot_lines.append(f"- `{mod}` ({count} outgoing imports)")

    hot_lines.append("\n## Trading Domain Hotspots\n")
    for category, items in hotspots["domain_hotspots"].items():
        hot_lines.append(f"### {category.replace('_', ' ').title()}\n")
        if items:
            for item in items:
                hot_lines.append(f"- `{item['symbol']}` in `{item['module']}`")
        else:
            hot_lines.append("- None detected statically")
        hot_lines.append("")

    (out_dir / "hotspots.md").write_text("\n".join(hot_lines), encoding="utf-8")

    print(f"Code graph successfully built in {out_dir}/")
    print(f"- Scanned {len(data['modules'])} modules")
    print(f"- Indexed {len(data['symbol_map'])} unique symbols")


def cmd_depends_on(args):
    dep_file = Path(".graphify/dependencies.json")
    if not dep_file.exists():
        print("Graph not built yet. Run `python tools/code_graph.py build` first.")
        return
    data = json.loads(dep_file.read_text(encoding="utf-8"))
    import_graph = data["import_graph"]

    target = args.module
    print(f"Modules importing/depending on `{target}`:")
    found = False
    for mod, deps in import_graph.items():
        if any(target in d for d in deps):
            print(f"  - {mod}")
            found = True
    if not found:
        print("  (None found or module not in import graph)")


def cmd_callers(args):
    mod_file = Path(".graphify/modules.json")
    if not mod_file.exists():
        print("Graph not built yet. Run `python tools/code_graph.py build` first.")
        return
    modules = json.loads(mod_file.read_text(encoding="utf-8"))

    symbol = args.symbol
    print(f"Callers / usages of `{symbol}`:")
    found = False
    for mod_name, mod_info in modules.items():
        for call in mod_info.get("calls", []):
            if symbol in call.get("called", ""):
                print(f"  - In `{mod_name}` (`{mod_info['file_path']}` line {call.get('lineno')}): caller `{call.get('caller')}` -> called `{call.get('called')}`")
                found = True
    if not found:
        print("  (No direct static calls found)")


def cmd_symbol(args):
    sym_file = Path(".graphify/symbols.json")
    if not sym_file.exists():
        print("Graph not built yet. Run `python tools/code_graph.py build` first.")
        return
    symbols = json.loads(sym_file.read_text(encoding="utf-8"))

    name = args.name
    if name in symbols:
        print(f"Definition(s) for symbol `{name}`:")
        for defn in symbols[name]:
            print(f"  - Type: {defn['type']}")
            print(f"    Module: {defn['module']}")
            print(f"    File: {defn['file']} (line {defn['lineno']})")
            if defn.get('bases'):
                print(f"    Bases: {defn['bases']}")
            if defn.get('methods'):
                print(f"    Methods: {defn['methods']}")
    else:
        print(f"Symbol `{name}` not found in index.")


def cmd_hotspots(args):
    hot_file = Path(".graphify/hotspots.md")
    if not hot_file.exists():
        print("Graph not built yet. Run `python tools/code_graph.py build` first.")
        return
    print(hot_file.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Lightweight AST Code Graph & Dependency Analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Build code graph and generate JSON/Markdown reports")

    p_dep = subparsers.add_parser("depends-on", help="Find modules depending on target module")
    p_dep.add_argument("module", help="Module name query")

    p_call = subparsers.add_parser("callers", help="Find callers/usages of a function or symbol")
    p_call.add_argument("symbol", help="Symbol/function name query")

    p_sym = subparsers.add_parser("symbol", help="Lookup symbol definition and location")
    p_sym.add_argument("name", help="Symbol name query")

    subparsers.add_parser("hotspots", help="Display architectural and domain hotspots")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "depends-on":
        cmd_depends_on(args)
    elif args.command == "callers":
        cmd_callers(args)
    elif args.command == "symbol":
        cmd_symbol(args)
    elif args.command == "hotspots":
        cmd_hotspots(args)


if __name__ == "__main__":
    main()
