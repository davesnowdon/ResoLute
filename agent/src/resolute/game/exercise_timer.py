"""Exercise timer tracking for timed practice sessions."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ExerciseState(str, Enum):
    """State of an exercise session."""

    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass
class ExerciseSession:
    """Represents an active exercise session."""

    player_id: str
    exercise_id: int
    exercise_name: str
    duration_seconds: int
    started_at: datetime = field(default_factory=datetime.utcnow)
    state: ExerciseState = ExerciseState.IN_PROGRESS
    destination_location_id: int | None = None

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.utcnow() - self.started_at).total_seconds()

    @property
    def remaining_seconds(self) -> float:
        """Get remaining time in seconds."""
        return max(0, self.duration_seconds - self.elapsed_seconds)

    @property
    def is_complete(self) -> bool:
        """Check if the exercise timer has completed."""
        return self.elapsed_seconds >= self.duration_seconds

    @property
    def progress_percent(self) -> float:
        """Get progress as a percentage (0-100)."""
        if self.duration_seconds == 0:
            return 100.0
        return min(100.0, (self.elapsed_seconds / self.duration_seconds) * 100)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "player_id": self.player_id,
            "exercise_id": self.exercise_id,
            "exercise_name": self.exercise_name,
            "duration_seconds": self.duration_seconds,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "remaining_seconds": round(self.remaining_seconds, 1),
            "progress_percent": round(self.progress_percent, 1),
            "state": self.state.value,
            "is_complete": self.is_complete,
            "destination_location_id": self.destination_location_id,
        }


class ExerciseTimer:
    """Manages exercise sessions for all players."""

    def __init__(self):
        self._sessions: dict[str, ExerciseSession] = {}
        self._completion_callbacks: dict[str, Callable] = {}

    def start_session(
        self,
        player_id: str,
        exercise_id: int,
        exercise_name: str,
        duration_seconds: int,
        destination_location_id: int | None = None,
    ) -> ExerciseSession:
        """Start a new exercise session for a player."""
        # Cancel any existing session
        if player_id in self._sessions:
            self.cancel_session(player_id)

        session = ExerciseSession(
            player_id=player_id,
            exercise_id=exercise_id,
            exercise_name=exercise_name,
            duration_seconds=duration_seconds,
            destination_location_id=destination_location_id,
        )
        self._sessions[player_id] = session
        return session

    def get_session(self, player_id: str) -> ExerciseSession | None:
        """Get the current exercise session for a player."""
        session = self._sessions.get(player_id)
        if session and session.is_complete and session.state == ExerciseState.IN_PROGRESS:
            session.state = ExerciseState.COMPLETED
        return session

    def check_session(self, player_id: str) -> dict | None:
        """Check the status of a player's exercise session."""
        session = self.get_session(player_id)
        if session is None:
            return None
        return session.to_dict()

    def complete_session(self, player_id: str) -> ExerciseSession | None:
        """Complete and remove an exercise session."""
        session = self._sessions.pop(player_id, None)
        if session:
            session.state = ExerciseState.COMPLETED
        return session

    def cancel_session(self, player_id: str) -> ExerciseSession | None:
        """Cancel and remove an exercise session."""
        session = self._sessions.pop(player_id, None)
        if session:
            session.state = ExerciseState.EXPIRED
        return session

    def has_active_session(self, player_id: str) -> bool:
        """Check if a player has an active exercise session."""
        session = self._sessions.get(player_id)
        return session is not None and session.state == ExerciseState.IN_PROGRESS

    def can_complete(self, player_id: str) -> bool:
        """Check if a player can complete their exercise (timer finished)."""
        session = self.get_session(player_id)
        return session is not None and session.is_complete

    async def wait_for_completion(
        self, player_id: str, check_interval: float = 1.0
    ) -> ExerciseSession | None:
        """Wait for an exercise session to complete (useful for testing)."""
        while True:
            session = self.get_session(player_id)
            if session is None:
                return None
            if session.is_complete:
                return session
            await asyncio.sleep(check_interval)


# Global timer instance
_timer: ExerciseTimer | None = None


def get_exercise_timer() -> ExerciseTimer:
    """Get the global exercise timer instance."""
    global _timer
    if _timer is None:
        _timer = ExerciseTimer()
    return _timer
