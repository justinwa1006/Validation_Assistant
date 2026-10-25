"""PySide6 없이(스텁 Qt) UI 구성 코드가 끝까지 실행되는지 검사한다.

실제 렌더링/이벤트는 검증하지 못한다. init_ui 분해나 위젯 코드를 고친 뒤 NameError/TypeError 같은
회귀를 빠르게 잡는 용도이며, 최종 확인은 앱을 직접 실행해서 해야 한다.
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path

import tests.conftest  # noqa: F401
from tools import qt_stub

ROOT = Path(__file__).resolve().parent.parent


class UiStructureTest(unittest.TestCase):
    @unittest.skipUnless(ROOT.name.isidentifier(), "패키지 임포트를 위해 폴더 이름이 식별자여야 함")
    def test_window_builds_with_stub_qt(self):
        qt_stub.install()
        sys.path.insert(0, str(ROOT.parent))
        try:
            engine = importlib.import_module(f"{ROOT.name}.engine")

            class Harness(engine.ValidationAssistant):
                def __getattr__(self, name):
                    if name.startswith("__"):
                        raise AttributeError(name)
                    return qt_stub.Rec(f"self.{name}")

            qt_stub.LOG.clear()
            Harness()
            created = [line for line in qt_stub.LOG if line.startswith("NEW ")]
            self.assertGreater(len(created), 300)
            self.assertTrue(any("QPushButton" in line for line in created))
        finally:
            sys.path.remove(str(ROOT.parent))

    def test_init_ui_is_a_thin_orchestrator(self):
        tree = ast.parse((ROOT / "ui_main.py").read_text(encoding="utf-8"))
        init_ui = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "init_ui")
        self.assertLess(init_ui.end_lineno - init_ui.lineno + 1, 30)


if __name__ == "__main__":
    unittest.main()

