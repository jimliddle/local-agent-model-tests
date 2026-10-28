"""Evaluate small pure-function fixtures in a separate restricted process."""
import ast
import builtins
import copy
import json
from pathlib import Path
import resource
import sys

from tasks import TASKS

SAFE = {k: getattr(builtins, k) for k in (
    "len", "range", "sorted", "set", "list", "tuple", "dict", "int", "str", "bool",
    "enumerate", "zip", "min", "max", "sum", "all", "any", "abs", "ValueError", "TypeError",
    "isinstance", "map", "filter", "reversed", "ord", "chr", "float", "round", "divmod", "repr")}


def syntax(source):
    tree = ast.parse(source)
    if not tree.body or any(not isinstance(n, ast.FunctionDef) for n in tree.body):
        raise ValueError("Only function definitions are permitted")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal)):
            raise ValueError("Imports, classes and global/nonlocal statements are not permitted")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Dunder names are not permitted")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("Private attributes are not permitted")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise ValueError("Decorators are not permitted")
    return tree


def evaluate(source, task, phase):
    tree = syntax(source)
    if phase == "syntax":
        return {"ok": True, "passed": 1, "total": 1}
    scope = {"__builtins__": SAFE}
    exec(compile(tree, "solution.py", "exec"), scope)
    cases = TASKS[task][phase]
    failures = []
    for index, (args, expected) in enumerate(cases):
        arguments = copy.deepcopy(args)
        try:
            actual = scope[task](*arguments)
            ok = actual == expected and arguments == args
            detail = {"actual": repr(actual)[:200], "expected": expected}
        except Exception as error:
            ok = isinstance(expected, dict) and expected.get("raises") == type(error).__name__
            detail = {"exception": type(error).__name__, "expected": expected}
        if not ok:
            failures.append({"case": index, **detail})
    return {"ok": not failures, "passed": len(cases)-len(failures), "total": len(cases), "failures": failures}


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    try:
        result = evaluate(Path(sys.argv[1]).read_text(), sys.argv[2], sys.argv[3])
    except Exception as error:
        result = {"ok": False, "error": type(error).__name__, "message": str(error)[:300]}
    print(json.dumps(result))
