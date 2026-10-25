"""프롬프트 상수의 구조 검사. 프롬프트를 수정하면 이 테스트가 회귀를 잡아준다."""
import json
import unittest

import tests.conftest  # noqa: F401
import prompt_data as pd
from core.prompt_checks import check_analysis_output, check_tc_item, extract_json_blocks


class SystemInstructionTest(unittest.TestCase):
    def test_has_missing_value_policy(self):
        self.assertIn("[MISSING-VALUE POLICY]", pd.SYSTEM_BASE_INSTRUCTION)
        self.assertIn("TBD", pd.SYSTEM_BASE_INSTRUCTION)

    def test_quantitative_mandate_is_scoped_to_known_values(self):
        # '정량 수치 필수'가 '지어내라'로 읽히지 않도록 범위가 한정되어야 한다
        self.assertIn("WHEN the value is given in, or directly derivable from", pd.SYSTEM_BASE_INSTRUCTION)

    def test_field_order_and_anti_copy_rules(self):
        self.assertIn("Field Order", pd.SYSTEM_BASE_INSTRUCTION)
        self.assertIn("FORMAT ONLY", pd.SYSTEM_BASE_INSTRUCTION)


class AnalysisFewShotTest(unittest.TestCase):
    def test_every_domain_example_is_valid_and_evidence_first(self):
        for key, shots in pd.FEW_SHOTS.items():
            blocks = extract_json_blocks(shots["analysis"])
            self.assertGreaterEqual(len(blocks), 3, key)
            for block in blocks:
                report = check_analysis_output("```json\n" + block + "\n```")
                self.assertTrue(report["ok"], f"{key}: {report['problems']}")

    def test_every_domain_covers_pass_fail_inconclusive_or_edge(self):
        for key, shots in pd.FEW_SHOTS.items():
            results = {json.loads(b)["result"] for b in extract_json_blocks(shots["analysis"])}
            self.assertIn("FAIL", results, key)
            self.assertIn("INCONCLUSIVE", results, key)

    def test_edge_examples_appended_exactly_once(self):
        for key, shots in pd.FEW_SHOTS.items():
            self.assertEqual(shots["analysis"].count("FAIL CASE"), 1, key)


class GenerationFewShotTest(unittest.TestCase):
    def test_every_example_tc_is_symmetric_and_quantitative(self):
        for key, shots in pd.FEW_SHOTS.items():
            for block in extract_json_blocks(shots["generation"]):
                for item in json.loads(block)["test_cases"]:
                    self.assertEqual(check_tc_item(item), [], f"{key}/{item['tc_id']}")

    def test_automotive_example_shows_boundary_and_tbd(self):
        items = json.loads(extract_json_blocks(pd.FEW_SHOTS["automotive"]["generation"])[0])["test_cases"]
        categories = {i["category"] for i in items}
        self.assertTrue({"Positive", "Boundary", "Negative"} <= categories)
        self.assertTrue(any("TBD" in line for i in items for line in i["expected_results"]))


class PromptSizeTest(unittest.TestCase):
    def test_domain_prompt_skeleton_stays_under_limit(self):
        for key, shots in pd.FEW_SHOTS.items():
            addendum = pd.DOMAIN_SYSTEM_ADDENDUM.get(key, "")
            skeleton = pd.SYSTEM_BASE_INSTRUCTION + addendum + shots["analysis"]
            # 사용자 입력/증적을 위한 여유 공간(약 4,000자)을 남겨야 한다
            self.assertLess(len(skeleton), pd.MAX_PROMPT_CHARS - 4000, f"{key}: {len(skeleton)}")


if __name__ == "__main__":
    unittest.main()

