"""Result type for consistent error handling."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    """A Result type for consistent error handling.

    Use Result.ok(value) for success, Result.err(message) for errors.

    Example:
        def get_player(player_id: str) -> Result[Player]:
            player = repo.get_by_id(player_id)
            if player is None:
                return Result.err("Player not found")
            return Result.ok(player)

        result = get_player("123")
        if result.is_err:
            return error_message(result.error)
        player = result.unwrap()
    """

    _value: T | None = None
    _error: str | None = None

    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        """Create a successful result with a value."""
        return cls(_value=value)

    @classmethod
    def err(cls, error: str) -> "Result[T]":
        """Create an error result with a message."""
        return cls(_error=error)

    @property
    def is_ok(self) -> bool:
        """Check if this result is successful."""
        return self._error is None

    @property
    def is_err(self) -> bool:
        """Check if this result is an error."""
        return self._error is not None

    @property
    def error(self) -> str | None:
        """Get the error message, or None if successful."""
        return self._error

    def unwrap(self) -> T:
        """Get the value, or raise ValueError if this is an error.

        Raises:
            ValueError: If this result is an error.
        """
        if self._error is not None:
            raise ValueError(self._error)
        return self._value  # type: ignore

    def unwrap_or(self, default: T) -> T:
        """Get the value, or return default if this is an error."""
        if self._error is not None:
            return default
        return self._value  # type: ignore

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for API/tool responses.

        Returns {"error": message} for errors, or the value's to_dict()
        if it has one, otherwise {"data": value}.
        """
        if self._error is not None:
            return {"error": self._error}
        if hasattr(self._value, "to_dict"):
            return self._value.to_dict()  # type: ignore
        if isinstance(self._value, dict):
            return self._value
        return {"data": self._value}
