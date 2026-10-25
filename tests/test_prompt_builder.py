import unittest

import tests.conftest  # noqa: F401
from core.prompt_builder import build_tc_review_prompt, build_validation_analysis_prompt

ARGS = dict(
    system_instruction="SYS", few_shot="SHOT", domain_role="ROLE", domain_rules="RULES",
    domain_evidence="EVID", tc_name="TC_1", tc_information="INFO", actual_result="ACT",
    analysis_purpose="원인 분석", analysis_question="",
)


class AnalysisPromptTest(unittest.TestCase):
    def test_section_order(self):
        text = build_validation_analysis_prompt(**ARGS)
        order = ["SYS", "SHOT", "너는 ROLE이다.", "[Validation Information]", "[Evidence Summary]",
                 "[[EVIDENCE_PREVIEW]]", "[Analysis Rules]"]
        positions = [text.index(token) for token in order]
        self.assertEqual(positions, sorted(positions))

    def test_default_question_when_empty(self):
        self.assertIn("차이 원인을 정량 분석하라", build_validation_analysis_prompt(**ARGS))

    def test_user_input_cannot_inject_placeholders(self):
        args = dict(ARGS, tc_name="__PURPOSE__", actual_result="__TC_NAME__")
        text = build_validation_analysis_prompt(**args)
        self.assertIn("TC Name: __PURPOSE__", text)
        self.assertIn("Actual Result / Issue: __TC_NAME__", text)

    def test_rules_include_verdict_and_tbd_policy(self):
        text = build_validation_analysis_prompt(**ARGS)
        self.assertIn("result 기준", text)
        self.assertIn("TBD", text)


class ReviewPromptTest(unittest.TestCase):
    def test_fields(self):
        text = build_tc_review_prompt(
            system_instruction="SYS", domain_role="ROLE", domain_rules="RULES",
            tc_name="TC_1", purpose="P", expected="E",
        )
        for token in ("TC Name: TC_1", "Purpose: P", "Expected Result: E", "[Review Rules]"):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()

