import json
import os
import tempfile
import unittest

import tests.conftest  # noqa: F401
from core.atomic_io import atomic_write_json, atomic_write_text


class AtomicIoTest(unittest.TestCase):
    def test_writes_valid_json_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.json")
            atomic_write_json(path, {"이름": "도어 잠금", "n": [1, 2]})
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"이름": "도어 잠금", "n": [1, 2]})

    def test_failed_serialization_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.json")
            atomic_write_json(path, {"ok": 1})
            with self.assertRaises(TypeError):
                atomic_write_json(path, {"bad": object()})
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"ok": 1})

    def test_no_temp_files_left_behind(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.json")
            atomic_write_json(path, [1])
            try:
                atomic_write_json(path, {"bad": object()})
            except TypeError:
                pass
            self.assertEqual(sorted(os.listdir(d)), ["a.json"])

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.txt")
            atomic_write_text(path, "one")
            atomic_write_text(path, "two")
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "two")


if __name__ == "__main__":
    unittest.main()

