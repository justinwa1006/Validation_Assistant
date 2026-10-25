import json
import unittest

import tests.conftest  # noqa: F401
from core.prompt_checks import (
    check_analysis_output, check_tc_item, find_vague_phrases, parse_model_output, unsupported_numbers,
)


def _analysis(order_ok=True, result="PASS"):
    base = {
        "evidence_status": "SUFFICIENT", "observations": ["a"], "gaps": [], "pass_factors": ["p"],
        "fail_factors": [], "result": result, "confidence": "HIGH", "risk": "LOW", "summary": "ok",
    }
    if not order_ok:
        base = {"result": result, "confidence": "HIGH", "risk": "LOW", "summary": "ok",
                "evidence_status": "SUFFICIENT", "observations": ["a"], "gaps": []}
    return "```json\n" + json.dumps(base, ensure_ascii=False) + "\n```"


class TcItemTest(unittest.TestCase):
    def test_asymmetric_steps_detected(self):
        problems = check_tc_item({"steps": ["1. a", "2. b"], "expected_results": ["1. x == 1"]})
        self.assertTrue(any("불일치" in p for p in problems))

    def test_vague_expected_detected(self):
        problems = check_tc_item({"steps": ["1. a"], "expected_results": ["1. 입력이 정상 감지된다."]})
        self.assertTrue(problems)

    def test_tbd_is_accepted(self):
        self.assertEqual(check_tc_item({"steps": ["1. a"], "expected_results": ["1. 값 == TBD (사양 미정)"]}), [])

    def test_quantitative_passes(self):
        self.assertEqual(check_tc_item({"steps": ["1. a"], "expected_results": ["1. 전이 시간 <= 150ms"]}), [])


class AnalysisOutputTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(check_analysis_output(_analysis())["ok"])

    def test_bad_enum(self):
        report = check_analysis_output(_analysis(result="PASS | FAIL"))
        self.assertFalse(report["ok"])

    def test_evidence_after_verdict_flagged(self):
        report = check_analysis_output(_analysis(order_ok=False))
        self.assertTrue(any("뒤에 나온 근거" in p for p in report["problems"]))

    def test_invalid_json(self):
        self.assertFalse(check_analysis_output("not json")["ok"])

    def test_parse_without_code_fence(self):
        self.assertEqual(parse_model_output('{"a": 1}'), {"a": 1})


class HelperTest(unittest.TestCase):
    def test_vague_phrases(self):
        self.assertIn("적절히", find_vague_phrases("적절히 동작한다"))

    def test_unsupported_numbers(self):
        self.assertEqual(unsupported_numbers("전이 210ms, 기준 150ms", "log 20.260s 150ms"), {"210"})


if __name__ == "__main__":
    unittest.main()

