"""함수 길이 상한(래칫). 새로 큰 함수가 생기는 것을 막고, 기존 큰 함수는 줄어들 때만 허용한다.

기존 대형 함수는 ALLOWED_LONG 에 현재 길이로 등록되어 있다. 리팩토링으로 줄이면 숫자를 낮추고,
새 함수는 DEFAULT_LIMIT 줄을 넘기지 않아야 한다.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIMIT = 120
ALLOWED_LONG = {
    ("unified_window.py", "create_window_class"): 260,
    ("automotive.py", "open_signal_mapping_dialog"): 186,
    ("ui_main.py", "open_quick_validation_dialog"): 150,
    ("ui_main.py", "update_mode_ui"): 148,
    ("ui_main.py", "open_quick_tc_dialog"): 137,
    ("storage.py", "load_tc"): 132,
    ("ui_components.py", "_u_apply_example_placeholders"): 122,
    ("ai_engine.py", "add_next_actions_section"): 121,
    ("ai_engine.py", "add_event_timeline_section"): 120,
}


class ComplexityBudgetTest(unittest.TestCase):
    def test_no_new_long_functions(self):
        violations = []
        for path in sorted(list(ROOT.glob("*.py")) + list((ROOT / "core").glob("*.py"))):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = node.end_lineno - node.lineno + 1
                    key = (str(path.relative_to(ROOT)).replace("\\", "/"), node.name)
                    limit = ALLOWED_LONG.get(key, DEFAULT_LIMIT)
                    if length > limit:
                        violations.append(f"{key[0]}:{key[1]} {length}줄 (상한 {limit})")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()

