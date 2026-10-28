"""Fixture controller; no arbitrary commands or paths from the model."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CHECKS = ("syntax", "unit", "integration")


class Controller:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.state_file = self.workspace / "state.json"
        self.state = json.loads(self.state_file.read_text())

    def save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def digest(self):
        return hashlib.sha256((self.workspace/"solution.py").read_bytes()).hexdigest()

    def check(self, check):
        if check not in CHECKS:
            raise ValueError("Unknown check")
        current = self.digest()
        for predecessor in CHECKS[:CHECKS.index(check)]:
            if self.state["receipts"].get(predecessor) != current:
                return {"ok": False, "reason": "Missing fresh passing predecessor", "predecessor": predecessor}
        if check == "unit" and self.state.get("inject_transient") and not self.state.get("injected"):
            self.state["injected"] = True
            result = {"ok": False, "simulated": True, "reason": "Temporary test-runner failure; no source edit needed. Retry unit once."}
        else:
            result = score(self.workspace, self.state["task"], check)
        self.state["checks"].append({"check": check, "source_hash": current, "result": result})
        if result["ok"] and current == self.digest():
            self.state["receipts"][check] = current
        else:
            for name in CHECKS[CHECKS.index(check):]:
                self.state["receipts"].pop(name, None)
        self.save()
        return {"check": check, **result}

    def action(self, name, args):
        if name == "read_source":
            return {"source": (self.workspace/"solution.py").read_text()}
        if name == "write_source":
            source = args.get("source")
            if not isinstance(source, str) or not 1 <= len(source) <= 12000:
                raise ValueError("Source must be 1..12000 characters")
            (self.workspace/"solution.py").write_text(source)
            self.state["receipts"] = {}
            self.save()
            return {"written": True, "source_hash": self.digest()}
        if name == "run_check":
            return self.check(args["check"])
        if name == "run_pipeline":
            results = []
            for check in CHECKS:
                result = self.check(check)
                results.append(result)
                if not result["ok"]:
                    break
            return {"results": results, "complete": len(results) == 3 and all(r["ok"] for r in results)}
        if name == "run_plan":
            if args.get("nodes") is not None:
                nodes = args["nodes"]
                expected = [{"check": c, "after": CHECKS[i-1] if i else "none"} for i,c in enumerate(CHECKS)]
                if nodes != expected:
                    raise ValueError("Provide syntax after none, unit after syntax, integration after unit; no other nodes allowed")
                self.state["plan"] = {"nodes": nodes, "source_hash": self.digest(), "completed": []}
                self.save()
            graph = self.state.get("plan")
            if not graph or graph["source_hash"] != self.digest():
                return {"ok": False, "reason": "No plan for current source; author a new plan"}
            results = []
            for node in graph["nodes"]:
                if node["check"] in graph["completed"]:
                    continue
                if graph["source_hash"] != self.digest():
                    return {"ok": False, "reason": "Source changed; plan invalidated", "results": results}
                result = self.check(node["check"])
                results.append(result)
                if not result["ok"]:
                    return {"ok": False, "results": results, "resume": "Call run_plan with no nodes to resume after resolving the failure"}
                graph["completed"].append(node["check"])
                self.save()
            return {"ok": True, "results": results, "complete": len(graph["completed"]) == 3}
        raise ValueError("Unknown action")


def score(workspace, task, phase):
    start = time.monotonic()
    # Generated functions cannot access home files, write outside their fixture,
    # or use the network. Python also exposes only a small builtin set.
    policy = '(version 1)(allow default)(deny network*)(deny file-write*)' + \
        '(deny file-read* (subpath ' + json.dumps(str(Path.home())) + '))' + \
        '(allow file-read* (subpath ' + json.dumps(str(HERE)) + '))' + \
        '(allow file-read* (subpath ' + json.dumps(str(workspace)) + '))'
    try:
        result = subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, sys.executable,
                                 "-B", str(HERE/"evaluate.py"), str(workspace/"solution.py"), task, phase],
                                capture_output=True, text=True, timeout=5,
                                env={"PATH":"/usr/bin:/bin:/opt/homebrew/bin", "PYTHONDONTWRITEBYTECODE":"1"})
        data = json.loads(result.stdout) if result.returncode == 0 else {"ok":False, "error":"evaluator_exit", "exit":result.returncode, "stderr":result.stderr[:300]}
    except (subprocess.TimeoutExpired, ValueError):
        data = {"ok":False, "error":"evaluator_timeout_or_bad_response"}
    return {**data, "seconds": time.monotonic()-start}


if __name__ == "__main__":
    try:
        controller = Controller(sys.argv[1])
        result = controller.action(sys.argv[2], json.load(sys.stdin))
    except Exception as error:
        result = {"ok":False, "error":type(error).__name__, "message":str(error)[:300]}
    print(json.dumps(result))
