"""Central enums and immutable contracts used by AI, QA and UI layers."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class AppMode(StrEnum):
    VALIDATION_ANALYSIS = "Validation Analysis"
    TC_GENERATION = "TC Generation"
    TC_REVIEW = "TC Review"


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    EVIDENCE_INSUFFICIENT = "EVIDENCE INSUFFICIENT"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class ReviewVerdict(StrEnum):
    PASS = "PASS"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"


class RuleType(StrEnum):
    VALUE = "VALUE"
    TRANSITION = "TRANSITION"
    TIME_LIMIT = "TIME_LIMIT"
    DURATION = "DURATION"
    SEQUENCE = "SEQUENCE"
    COUNT = "COUNT"
    ABSENCE = "ABSENCE"
    RANGE = "RANGE"
