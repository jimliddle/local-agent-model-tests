import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from control import Controller
from evaluate import evaluate, syntax
from tasks import TASKS

NODES = [{"check":"syntax","after":"none"},{"check":"unit","after":"syntax"},{"check":"integration","after":"unit"}]


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/"solution.py").write_text(TASKS["ranges"]["source"])
        (self.root/"state.json").write_text(json.dumps({"task":"ranges","receipts":{},"checks":[]}))
        self.c = Controller(self.root)

    @patch("control.score", return_value={"ok":True})
    def test_sequence(self, mock):
        self.assertTrue(self.c.action("run_plan", {"nodes":NODES})["complete"])
        self.assertEqual(mock.call_count, 3)
        self.c.action("run_plan", {})
        self.assertEqual(mock.call_count, 3)

    @patch("control.score", return_value={"ok":True})
    def test_missing_predecessor(self, mock):
        self.assertFalse(self.c.check("unit")["ok"])
        mock.assert_not_called()

    @patch("control.score", side_effect=[{"ok":True},{"ok":False},{"ok":True},{"ok":True}])
    def test_failure_resume(self, mock):
        self.assertFalse(self.c.action("run_plan", {"nodes":NODES})["ok"])
        self.assertEqual(mock.call_count,2)
        self.assertTrue(Controller(self.root).action("run_plan", {})["complete"])
        self.assertEqual(mock.call_count,4)

    @patch("control.score", return_value={"ok":True})
    def test_edit_invalidates(self, mock):
        self.c.action("run_plan", {"nodes":NODES})
        self.c.action("write_source", {"source":"def ranges(x):\n    return []\n"})
        self.assertFalse(self.c.action("run_plan", {})["ok"])
        self.assertFalse(self.c.check("integration")["ok"])

    @patch("control.score", side_effect=[{"ok":True},{"ok":False}])
    def test_script_stops(self, mock):
        self.assertFalse(self.c.action("run_pipeline", {})["complete"])
        self.assertEqual(mock.call_count,2)

    def test_invalid_graphs(self):
        for nodes in ([], NODES[::-1], NODES+[NODES[-1]], [{"check":"shell","after":"none"}]):
            with self.subTest(nodes=nodes), self.assertRaises(ValueError):
                self.c.action("run_plan", {"nodes":nodes})

    def test_execution_restrictions(self):
        for source in ("import os", "x=1", "def f():\n return ().__class__", "@open('x')\ndef f(): pass"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                syntax(source)

    def test_bad_sources_fail(self):
        for task,data in TASKS.items():
            self.assertFalse(evaluate(data["source"],task,"heldout")["ok"])

    def test_correct_source(self):
        source="def chunks(items, size):\n    if size <= 0:\n        raise ValueError()\n    return [items[i:i+size] for i in range(0, len(items), size)]\n"
        for phase in ("syntax","unit","integration","heldout"):
            self.assertTrue(evaluate(source,"chunks",phase)["ok"])

    def test_normal_python_builtins(self):
        source="def duration(text):\n    if not isinstance(text, str): raise ValueError()\n    parts = text.split(':')\n    if len(parts) != 3 or any(len(p) != 2 or not p.isascii() or not p.isdigit() for p in parts): raise ValueError()\n    h,m,s = map(int,parts)\n    if m > 59 or s > 59: raise ValueError()\n    return h*3600+m*60+s\n"
        for phase in ("syntax","unit","integration","heldout"):
            self.assertTrue(evaluate(source,"duration",phase)["ok"])

    @patch("control.score", return_value={"ok":True})
    def test_transient_once(self, mock):
        self.c.state["inject_transient"] = True
        self.c.check("syntax")
        self.assertFalse(self.c.check("unit")["ok"])
        self.assertTrue(self.c.check("unit")["ok"])
        self.assertEqual(mock.call_count,2)


if __name__ == "__main__":
    unittest.main()
