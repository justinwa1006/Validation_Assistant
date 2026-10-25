import unittest

import tests.conftest  # noqa: F401  (sys.path 설정)
from core.templating import fill_template


class FillTemplateTest(unittest.TestCase):
    def test_basic_replace(self):
        self.assertEqual(fill_template("A=__A__, B=__B__", {"__A__": "1", "__B__": "2"}), "A=1, B=2")

    def test_value_containing_placeholder_is_not_resubstituted(self):
        # 사용자 입력에 다른 플레이스홀더가 들어 있어도 재치환되면 안 된다 (템플릿 인젝션 방지)
        out = fill_template("TC=__TC__ / PURPOSE=__PURPOSE__", {"__TC__": "__PURPOSE__", "__PURPOSE__": "secret"})
        self.assertEqual(out, "TC=__PURPOSE__ / PURPOSE=secret")

    def test_prefix_keys_prefer_longest(self):
        out = fill_template("__A__ __A_LONG__", {"__A__": "x", "__A_LONG__": "y"})
        self.assertEqual(out, "x y")

    def test_empty_values_returns_template(self):
        self.assertEqual(fill_template("keep __A__", {}), "keep __A__")

    def test_non_string_values(self):
        self.assertEqual(fill_template("n=__N__", {"__N__": 3}), "n=3")


if __name__ == "__main__":
    unittest.main()

