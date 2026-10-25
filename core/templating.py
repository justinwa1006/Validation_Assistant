"""프롬프트 템플릿 치환 유틸리티 (Qt 의존 없음)."""
from __future__ import annotations

import re
from typing import Any, Mapping


def fill_template(template: str, values: Mapping[str, Any]) -> str:
    """플레이스홀더를 한 번에(single-pass) 치환한다.

    치환된 값 안에 다른 플레이스홀더(예: ``__XXX__``)가 들어 있어도 재치환하지 않는다.
    사용자 입력이 템플릿 구조를 바꾸는 것(템플릿 인젝션)을 막기 위한 동작이다.
    긴 키를 먼저 매칭하므로 키가 서로 접두사 관계여도 안전하다.
    """
    if not values:
        return template
    pattern = re.compile("|".join(re.escape(k) for k in sorted(values, key=len, reverse=True)))
    return pattern.sub(lambda m: str(values[m.group(0)]), template)

