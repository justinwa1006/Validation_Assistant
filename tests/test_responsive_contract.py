"""Regression tests for the responsive adapter contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_removed_restore_callback_cannot_regress():
    text = (ROOT / "unified_window.py").read_text(encoding="utf-8")
    assert "_restore_responsive_state" not in text
    assert "_restore_timer" not in text


def test_result_panel_positions_are_engine_owned():
    text = (ROOT / "ui_responsive.py").read_text(encoding="utf-8")
    assert ".setSizes(" not in text
    assert ".restoreState(" not in text
    assert "setContentsMargins(" not in text


def test_overflow_and_collapsible_features_exist():
    text = (ROOT / "ui_responsive.py").read_text(encoding="utf-8")
    assert "wrap_automotive_panel" in text
    assert "configure_evidence_group" in text
    assert "ScrollBarAsNeeded" in text
