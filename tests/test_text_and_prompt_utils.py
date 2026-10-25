import unittest

import tests.conftest  # noqa: F401
from core.prompt_text import (
    clean_prompt_block, coerce_rule_value, is_structural_line, light_alias_suffix,
    normalize_prompt_spacing, normalize_signal_match_name, numbered_items,
)
from core.text_utils import make_safe_filename, strip_existing_list_prefix


class TextUtilsTest(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(make_safe_filename('a<b>:c/"d"  e. '), "a_b__c__d_ e")
        self.assertEqual(make_safe_filename("   "), "Validation_Result")
        self.assertEqual(len(make_safe_filename("x" * 300)), 100)

    def test_strip_prefix(self):
        self.assertEqual(strip_existing_list_prefix("1. Step 2) - 입력"), "입력")
        self.assertEqual(strip_existing_list_prefix(None), "")


class PromptTextTest(unittest.TestCase):
    def test_numbered_items_ignores_numeric_sentences(self):
        items = numbered_items("1. 첫째\n2) 둘째\n13.5V 인가")
        self.assertEqual(items[0], ("1", "첫째"))
        self.assertEqual(items[1], ("2", "둘째"))
        self.assertEqual(items[2][1], "13.5V 인가")

    def test_coerce_rule_value(self):
        self.assertEqual(coerce_rule_value("0x10"), 16.0)
        self.assertEqual(coerce_rule_value("150ms"), 150.0)
        self.assertEqual(coerce_rule_value("locked"), "LOCKED")

    def test_signal_name_normalization(self):
        self.assertEqual(normalize_signal_match_name("Sig_DrvDoorLockSts"), "sig driver door lock status")

    def test_light_alias_suffix_is_deterministic(self):
        self.assertEqual(light_alias_suffix("abc"), light_alias_suffix("abc"))
        self.assertRegex(light_alias_suffix("abc"), r"^_[A-Z]\d$")

    def test_spacing_helpers(self):
        self.assertEqual(normalize_prompt_spacing("a  \n\n\n\nb\n"), "a\n\nb")
        self.assertEqual(clean_prompt_block("    x\n\n\n    y"), "x\n\ny")

    def test_structural_line(self):
        self.assertTrue(is_structural_line('"key": 1'))
        self.assertTrue(is_structural_line("{"))
        self.assertFalse(is_structural_line("[Analysis Rules]"))


if __name__ == "__main__":
    unittest.main()

