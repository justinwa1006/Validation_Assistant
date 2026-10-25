import unittest

import tests.conftest  # noqa: F401
from core.tc_review import build_rule_based_tc_review


def _tc(**overrides):
    base = {
        "tc_id": "TC_1", "title": "t", "preconditions": ["1. IGN_ON (0x02)"],
        "steps": ["1. 입력"], "expected_results": ["1. 전이 <= 150ms"],
        "risk": "HIGH", "risk_description": "영향",
    }
    base.update(overrides)
    return {"test_cases": [base]}


class RuleBasedReviewTest(unittest.TestCase):
    def test_clean_tc_passes(self):
        review = build_rule_based_tc_review(_tc())
        self.assertEqual(review["reviewed_test_cases"][0]["review_result"], "PASS")
        self.assertEqual(review["summary"]["pass_count"], 1)

    def test_asymmetric_steps_flagged(self):
        review = build_rule_based_tc_review(_tc(steps=["1. a", "2. b"]))
        item = review["reviewed_test_cases"][0]
        self.assertEqual(item["review_result"], "NEEDS_IMPROVEMENT")
        self.assertTrue(any("개수가 다릅니다" in i for i in item["issues"]))

    def test_tbd_has_its_own_message(self):
        review = build_rule_based_tc_review(_tc(expected_results=["1. 값 == TBD (사양 미정)"]))
        issues = review["reviewed_test_cases"][0]["issues"]
        self.assertTrue(any("사양 미정(TBD)" in i for i in issues))
        self.assertFalse(any("모호한 표현" in i for i in issues))

    def test_vague_phrase_flagged(self):
        review = build_rule_based_tc_review(_tc(expected_results=["1. 적절히 동작한다"]))
        issues = review["reviewed_test_cases"][0]["issues"]
        self.assertTrue(any("모호한 표현" in i for i in issues))

    def test_non_dict_input(self):
        self.assertEqual(build_rule_based_tc_review(None)["summary"]["total_count"], 0)


if __name__ == "__main__":
    unittest.main()

