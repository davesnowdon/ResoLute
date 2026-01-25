"""Progress repository for data access."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from resolute.db.models import PlayerProgress, ProgressState, ProgressType, SongSegment


class ProgressRepository:
    """Pure data access for PlayerProgress entities."""

    def __init__(self, session: Session):
        self.session = session

    def get(
        self, player_id: str, progress_type: str, reference_id: int
    ) -> PlayerProgress | None:
        """Get a specific progress entry."""
        result = self.session.execute(
            select(PlayerProgress)
            .where(PlayerProgress.player_id == player_id)
            .where(PlayerProgress.progress_type == progress_type)
            .where(PlayerProgress.reference_id == reference_id)
        )
        return result.scalar_one_or_none()

    def get_segment_progress(
        self, player_id: str, segment_id: int
    ) -> PlayerProgress | None:
        """Get progress for a specific segment."""
        return self.get(player_id, ProgressType.SEGMENT.value, segment_id)

    def create(
        self,
        player_id: str,
        progress_type: str,
        reference_id: int,
        state: str = ProgressState.NOT_STARTED.value,
    ) -> PlayerProgress:
        """Create a new progress entry."""
        progress = PlayerProgress(
            player_id=player_id,
            progress_type=progress_type,
            reference_id=reference_id,
            state=state,
        )
        self.session.add(progress)
        self.session.flush()
        return progress

    def mark_completed(self, progress: PlayerProgress) -> PlayerProgress:
        """Mark a progress entry as completed."""
        progress.state = ProgressState.COMPLETED.value
        progress.completed_at = datetime.now(datetime.UTC)
        self.session.flush()
        return progress

    def get_collected_segment_ids(self, player_id: str) -> set[int]:
        """Get IDs of all collected segments for a player."""
        result = self.session.execute(
            select(PlayerProgress.reference_id)
            .where(PlayerProgress.player_id == player_id)
            .where(PlayerProgress.progress_type == ProgressType.SEGMENT.value)
            .where(PlayerProgress.state == ProgressState.COMPLETED.value)
        )
        return {row[0] for row in result.all()}

    def get_collected_segments(self, player_id: str) -> list[SongSegment]:
        """Get all collected segments for a player."""
        collected_ids = self.get_collected_segment_ids(player_id)
        if not collected_ids:
            return []

        result = self.session.execute(
            select(SongSegment).where(SongSegment.id.in_(collected_ids))
        )
        return list(result.scalars().all())

    def count_collected_segments(self, player_id: str) -> int:
        """Count how many segments a player has collected."""
        return len(self.get_collected_segment_ids(player_id))
