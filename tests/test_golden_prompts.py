"""generate_prompt 결과가 저장된 기준(golden)과 같은지 검사한다.

의도한 프롬프트 변경이면 UPDATE_GOLDEN=1 python -m pytest tests/test_golden_prompts.py 로 기준을 갱신하고,
diff 를 리뷰한 뒤 커밋한다. Qt 는 tools/qt_stub 의 스텁으로 대체되므로 GUI 가 없어도 실행된다.
"""
import json
import os
import unittest
from pathlib import Path

import tests.conftest  # noqa: F401
from tools.golden_prompts import build_all

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "prompts.json"


class GoldenPromptTest(unittest.TestCase):
    def test_generate_prompt_matches_golden(self):
        current = build_all(str(ROOT))
        if os.environ.get("UPDATE_GOLDEN") == "1":
            GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(sorted(current), sorted(expected))
        changed = [key for key in expected if current[key] != expected[key]]
        self.assertEqual(changed, [], f"프롬프트가 기준과 다릅니다: {changed[:5]}")


if __name__ == "__main__":
    unittest.main()

