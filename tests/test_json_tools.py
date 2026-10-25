import json
import unittest

import tests.conftest  # noqa: F401
from core.json_tools import extract_json_from_text, repair_common_json_errors


class ExtractJsonTest(unittest.TestCase):
    def test_fenced_block(self):
        text = 'intro\n```json\n{"result": "PASS"}\n```\ntail'
        self.assertEqual(json.loads(extract_json_from_text(text)), {"result": "PASS"})

    def test_plain_object_with_surrounding_text(self):
        text = 'Here you go: {"a": {"b": 1}} thanks'
        self.assertEqual(json.loads(extract_json_from_text(text)), {"a": {"b": 1}})

    def test_braces_inside_strings_do_not_break_matching(self):
        text = 'x {"s": "} not end {", "n": 2} y'
        self.assertEqual(json.loads(extract_json_from_text(text)), {"s": "} not end {", "n": 2})

    def test_smart_quotes_and_html_entities(self):
        text = "{“result”: “PASS”}"
        self.assertEqual(json.loads(extract_json_from_text(text)), {"result": "PASS"})

    def test_marker(self):
        self.assertEqual(json.loads(extract_json_from_text('noise [JSON OUTPUT] {"k": 1}')), {"k": 1})

    def test_returns_none_for_non_json(self):
        self.assertIsNone(extract_json_from_text("no json here"))
        self.assertIsNone(extract_json_from_text(""))
        self.assertIsNone(extract_json_from_text('{"unterminated": '))


class RepairTest(unittest.TestCase):
    def test_python_literals_and_trailing_commas(self):
        raw = '```json\n{"a": True,\n "b": None,\n "c": [1,\n]\n}\n```'
        self.assertEqual(json.loads(repair_common_json_errors(raw)), {"a": True, "b": None, "c": [1]})

    def test_empty(self):
        self.assertEqual(repair_common_json_errors(None), "")


if __name__ == "__main__":
    unittest.main()

