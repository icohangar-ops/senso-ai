#!/usr/bin/env python3
"""Evidence check: production-quality Python — docstrings, type hints, logging.

Backs the README "Key Features" claim: every module under src/ carries a
module docstring; every top-level class and function carries a docstring;
every function/method is fully annotated; and the runtime modules
(authorization, retrieval_filter, rag_engine) define module loggers.

Runs offline: AST-scans the source tree. Exit 0 = held.
"""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LOGGING_MODULES = (
    "src/auth0_fga/authorization.py",
    "src/auth0_fga/retrieval_filter.py",
    "src/retrieval/rag_engine.py",
)


def _missing_param_annotations(func):
    return [
        arg.arg
        for arg in func.args.args + func.args.kwonlyargs
        if arg.arg not in ("self", "cls") and arg.annotation is None
    ]


def main():
    modules = sorted(p for p in (REPO_ROOT / "src").rglob("*.py"))
    assert modules, "no src modules found"
    checked_functions = 0
    for py_file in modules:
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(py_file.read_text())
        assert ast.get_docstring(tree) is not None, f"{rel}: module docstring missing"

        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                assert ast.get_docstring(node) is not None, f"{rel}: {node.name} docstring missing"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                missing = _missing_param_annotations(node)
                assert not missing, f"{rel}: {node.name} unannotated parameters {missing}"
                if not (node.name.startswith("__") and node.name.endswith("__") and node.name != "__init__"):
                    assert node.returns is not None, f"{rel}: {node.name} missing return annotation"
                checked_functions += 1
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        missing = _missing_param_annotations(sub)
                        assert not missing, f"{rel}: {node.name}.{sub.name} unannotated parameters {missing}"
                        if sub.name != "__init__":
                            assert sub.returns is not None, f"{rel}: {node.name}.{sub.name} missing return annotation"
                        checked_functions += 1

    for rel in LOGGING_MODULES:
        tree = ast.parse((REPO_ROOT / rel).read_text())
        has_logger = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and "logger" in target.id.lower() for target in node.targets)
            for node in tree.body
        )
        assert has_logger, f"{rel}: module logger missing"

    print(f"verify_code_quality: PASS ({len(modules)} modules, {checked_functions} functions checked: docstrings, full annotations, module loggers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
