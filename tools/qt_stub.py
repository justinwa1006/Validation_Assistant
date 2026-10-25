"""PySide6 가 없는 환경에서 UI 코드를 '기록 모드'로 실행하기 위한 스텁.

모든 Qt 클래스는 생성/메서드 호출을 LOG 에 남긴다. 리팩토링 전후의 LOG 가 같으면
위젯 생성/연결 순서와 인자가 보존된 것이다 (tools/record_ui.py, tools/compare_ui.py 참고).
실제 Qt 렌더링을 대체하는 것이 아니므로 최종 확인은 반드시 실제 앱 실행으로 해야 한다.
"""
from __future__ import annotations

import itertools
import re
import sys
import types

LOG: list[str] = []
_ids = itertools.count(1)


def _fmt(value) -> str:
    if isinstance(value, (Rec, StubBase)):
        return value._label
    text = repr(value)
    text = re.sub(r"0x[0-9a-fA-F]+", "0x?", text)
    return text


def _args(args, kwargs) -> str:
    parts = [_fmt(a) for a in args] + [f"{k}={_fmt(v)}" for k, v in kwargs.items()]
    return ", ".join(parts)


_ZERO_METHODS = {"count", "rowCount", "columnCount", "length", "size"}
_STR_METHODS = {"text", "toPlainText", "currentText", "objectName", "placeholderText", "windowTitle", "toolTip"}


class Rec:
    """호출/속성 접근을 기록하는 범용 객체."""

    def __init__(self, label: str):
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Rec(f"{self._label}.{name}")

    def __call__(self, *args, **kwargs):
        LOG.append(f"{self._label}({_args(args, kwargs)})")
        if self._label.rsplit(".", 1)[-1] in _ZERO_METHODS:
            return 0  # while layout.count(): ... 같은 루프가 끝나도록 정수를 돌려준다
        if self._label.rsplit(".", 1)[-1] in _STR_METHODS:
            return ""  # re.search(..., label.text()) 처럼 문자열을 기대하는 코드를 위해
        return Rec(f"{self._label}()#{next(_ids)}")

    def __setattr__(self, name, value):
        LOG.append(f"{self._label}.{name} = {_fmt(value)}")

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __bool__(self):
        return True

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return self._label


for _op in ("add", "sub", "mul", "truediv", "floordiv", "mod", "or", "and", "xor", "lshift", "rshift"):
    for _form in (f"__{_op}__", f"__r{_op}__"):
        setattr(Rec, _form, lambda self, other, _n=_op: Rec(f"({self._label} {_n} {_fmt(other)})"))
for _cmp in ("lt", "le", "gt", "ge"):
    setattr(Rec, f"__{_cmp}__", lambda self, other: True)
Rec.__neg__ = lambda self: Rec(f"-{self._label}")
Rec.__invert__ = lambda self: Rec(f"~{self._label}")


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Rec(f"{cls.__name__}.{name}")

    def __or__(cls, other):
        return Rec(f"{cls.__name__}|{_fmt(other)}")


class StubBase(metaclass=_Meta):
    def __init__(self, *args, **kwargs):
        object.__setattr__(self, "_label", f"{type(self).__name__}#{next(_ids)}")
        LOG.append(f"NEW {self._label}({_args(args, kwargs)})")

    def __getattr__(self, name):
        if name.startswith("__") or name == "_label":
            raise AttributeError(name)
        return Rec(f"{self._label}.{name}")

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return self._label


def _make_class(name: str):
    return _Meta(name, (StubBase,), {})


class _StubModule(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self._cache = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self._cache:
            self._cache[name] = _make_class(name) if name[:1].isupper() else Rec(f"{self.__name__}.{name}")
        return self._cache[name]


def install():
    for mod in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"):
        sys.modules[mod] = _StubModule(mod)
    # QWidget 계열을 상속하는 클래스가 있으므로 Signal 은 호출 가능한 객체여야 한다
    sys.modules["PySide6.QtCore"].Signal = lambda *a, **k: Rec("Signal")

