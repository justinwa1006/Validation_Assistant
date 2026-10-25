from pathlib import Path
import ast

ROOT = Path(__file__).parent


def test_prompt_data_budgets():
    ns = {}
    exec(compile((ROOT / "prompt_data.py").read_text(encoding="utf-8"), "prompt_data.py", "exec"), ns)
    assert ns["PROMPT_BUDGETS"] == {
        "TC Generation": 18000,
        "TC Review": 26000,
        "Validation Analysis": 36000,
    }
    assert ns["BLF_EXTRA_PROMPT_CHARS"] == 10000
    assert ns["MAX_PROMPT_CHARS"] == 48000


def test_engine_syntax_and_contract():
    text = (ROOT / "tc_engine.py").read_text(encoding="utf-8")
    ast.parse(text)
    assert "def get_prompt_budget" in text
    assert "def compact_prompt_for_budget" in text
    assert "current_length > absolute_limit" in text
    assert "current_length > recommended" in text
    assert "임의 절단하지 않았습니다" in text
