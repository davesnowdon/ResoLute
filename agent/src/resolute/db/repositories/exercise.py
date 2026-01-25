"""Exercise repository for data access."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from resolute.db.models import Exercise


class ExerciseRepository:
    """Pure data access for Exercise entities."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, exercise_id: int) -> Exercise | None:
        """Get an exercise by ID."""
        result = self.session.execute(select(Exercise).where(Exercise.id == exercise_id))
        return result.scalar_one_or_none()

    def get_random(
        self,
        exercise_type: str | None = None,
        min_difficulty: int | None = None,
        max_difficulty: int | None = None,
    ) -> Exercise | None:
        """Get a random exercise, optionally filtered by type and difficulty."""
        query = select(Exercise)

        if exercise_type:
            query = query.where(Exercise.exercise_type == exercise_type)

        if min_difficulty is not None:
            query = query.where(Exercise.difficulty >= min_difficulty)

        if max_difficulty is not None:
            query = query.where(Exercise.difficulty <= max_difficulty)

        query = query.order_by(func.random()).limit(1)
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def get_all_by_type(self, exercise_type: str) -> list[Exercise]:
        """Get all exercises of a specific type."""
        result = self.session.execute(
            select(Exercise).where(Exercise.exercise_type == exercise_type)
        )
        return list(result.scalars().all())
