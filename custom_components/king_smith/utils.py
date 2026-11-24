"""Utility classes and functions for the walkingpad integration."""

from typing import Generic, TypeVar

T = TypeVar("T")


class TemporaryValue(Generic[T]):
    """Generic temporary value with expiration."""

    def __init__(self) -> None:
        """Initialize temporary value."""
        self.has_value = False
        self.value: T | None = None
        self.expiration_timestamp: float = 0
        self.set_at_status_timestamp: float = 0

    def set(
        self,
        value: T,
        expiration_timestamp: float,
        *,
        set_at_status_timestamp: float = 0,
    ) -> None:
        """Set a temporary value with expiration."""
        self.has_value = True
        self.value = value
        self.expiration_timestamp = expiration_timestamp
        self.set_at_status_timestamp = set_at_status_timestamp

    def reset(self) -> None:
        """Reset the temporary value."""
        self.has_value = False
        self.value = None

    def get(self, current_timestamp: float, default: T) -> T:
        """Get the temporary value or default, checking expiration."""
        if self.has_value and current_timestamp > self.expiration_timestamp:
            self.reset()
        if self.has_value and self.value is not None:
            return self.value
        return default

    def peek(self, default: T) -> T:
        """Get the temporary value or default without checking expiration."""
        if self.has_value and self.value is not None:
            return self.value
        return default
