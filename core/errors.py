"""Typed exceptions for actionable user messages and reliable logging."""


class ValidationAssistantError(Exception):
    """Base exception for expected application failures."""


class UserInputError(ValidationAssistantError):
    """The user input is incomplete or malformed."""


class DataFormatError(ValidationAssistantError):
    """A JSON, DBC, BLF, Excel or project file has an invalid format."""


class AIResponseError(ValidationAssistantError):
    """The AI response cannot be parsed or violates its output contract."""


class EvidenceError(ValidationAssistantError):
    """Evidence is missing, ambiguous or inconsistent."""


class StorageError(ValidationAssistantError):
    """A persistent read/write operation failed."""
