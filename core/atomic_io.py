"""원자적 파일 쓰기 유틸리티 (Qt 의존 없음).

임시 파일에 먼저 쓴 뒤 ``os.replace`` 로 교체하므로, 쓰는 도중 프로세스가 종료되거나
직렬화에 실패해도 기존 파일은 손상되지 않는다.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def atomic_write_text(path: str | os.PathLike, text: str, encoding: str = "utf-8") -> None:
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".part", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: str | os.PathLike, data: Any, *, indent: int = 4) -> None:
    """JSON 직렬화를 먼저 끝낸 뒤 원자적으로 저장한다 (직렬화 실패 시 기존 파일 유지)."""
    text = json.dumps(data, ensure_ascii=False, indent=indent)
    atomic_write_text(path, text)

