"""SQLAlchemy models for ResoLute game."""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class LocationType(str, Enum):
    """Types of locations in the game world."""

    VILLAGE = "village"
    PATH = "path"
    TAVERN = "tavern"
    DUNGEON = "dungeon"


class ExerciseType(str, Enum):
    """Types of exercises players can complete."""

    RHYTHM = "rhythm"
    MELODY = "melody"
    HARMONY = "harmony"
    EAR_TRAINING = "ear_training"
    SIGHT_READING = "sight_reading"


class SkillType(str, Enum):
    """Types of player skills that can be improved."""

    RHYTHM = "rhythm"
    MELODY = "melody"
    HARMONY = "harmony"


# Mapping from SkillType to Player attribute names
SKILL_ATTR_MAP: dict[SkillType, str] = {
    SkillType.RHYTHM: "skill_rhythm",
    SkillType.MELODY: "skill_melody",
    SkillType.HARMONY: "skill_harmony",
}


class ProgressType(str, Enum):
    """Types of progress that can be tracked."""

    EXERCISE = "exercise"
    SEGMENT = "segment"
    SONG = "song"
    LOCATION = "location"


class ProgressState(str, Enum):
    """State of a progress entry."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Player(Base):
    """Player model storing character state."""

    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="Wandering Bard")
    level: Mapped[int] = mapped_column(default=1)
    xp: Mapped[int] = mapped_column(default=0)
    gold: Mapped[int] = mapped_column(default=0)
    reputation: Mapped[int] = mapped_column(default=0)

    # Skills (0-100 scale)
    skill_rhythm: Mapped[int] = mapped_column(default=10)
    skill_melody: Mapped[int] = mapped_column(default=10)
    skill_harmony: Mapped[int] = mapped_column(default=10)

    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    worlds: Mapped[list["World"]] = relationship(back_populates="player", cascade="all, delete")
    progress: Mapped[list["PlayerProgress"]] = relationship(
        back_populates="player", cascade="all, delete"
    )
    current_location: Mapped["Location | None"] = relationship(foreign_keys=[current_location_id])

    def update_skill(self, skill_type: "SkillType", delta: int) -> None:
        """Update a skill by the given delta, capping at 100."""
        attr_name = SKILL_ATTR_MAP[skill_type]
        current_value = getattr(self, attr_name)
        setattr(self, attr_name, min(100, current_value + delta))

    def to_dict(self) -> dict:
        """Convert player to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "xp": self.xp,
            "gold": self.gold,
            "reputation": self.reputation,
            "skills": {
                SkillType.RHYTHM.value: self.skill_rhythm,
                SkillType.MELODY.value: self.skill_melody,
                SkillType.HARMONY.value: self.skill_harmony,
            },
            "current_location_id": self.current_location_id,
        }


class World(Base):
    """World model - each player has their own unique world."""

    __tablename__ = "worlds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    theme: Mapped[str] = mapped_column(String(100))
    story_arc: Mapped[str] = mapped_column(Text)
    final_monster: Mapped[str] = mapped_column(String(200))
    rescue_target: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="worlds")
    locations: Mapped[list["Location"]] = relationship(
        back_populates="world", cascade="all, delete", lazy="selectin"
    )

    def to_dict(self) -> dict:
        """Convert world to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "theme": self.theme,
            "story_arc": self.story_arc,
            "final_monster": self.final_monster,
            "rescue_target": self.rescue_target,
            "locations": [
                loc.to_dict() for loc in sorted(self.locations, key=lambda x: x.order_index)
            ],
        }


class Location(Base):
    """Location model - villages, paths, taverns, dungeons."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    location_type: Mapped[str] = mapped_column(String(20), default=LocationType.VILLAGE.value)
    exercise_focus: Mapped[str] = mapped_column(String(50), nullable=True)
    order_index: Mapped[int] = mapped_column(default=0)
    is_unlocked: Mapped[bool] = mapped_column(default=False)

    # Relationships
    world: Mapped["World"] = relationship(back_populates="locations")
    segments: Mapped[list["SongSegment"]] = relationship(
        back_populates="location", lazy="selectin"
    )

    def to_dict(self, include_segments: bool = True) -> dict:
        """Convert location to dictionary for API responses.

        Args:
            include_segments: Whether to include segments (requires eager loading in async).
        """
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.location_type,
            "exercise_focus": self.exercise_focus,
            "order_index": self.order_index,
            "is_unlocked": self.is_unlocked,
        }
        if include_segments:
            result["segments"] = [seg.to_dict() for seg in self.segments]
        return result


class Exercise(Base):
    """Pre-defined exercise library."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    exercise_type: Mapped[str] = mapped_column(String(50))
    difficulty: Mapped[int] = mapped_column(default=1)  # 1-10 scale
    duration_seconds: Mapped[int] = mapped_column(default=60)
    instructions: Mapped[str] = mapped_column(Text)
    xp_reward: Mapped[int] = mapped_column(default=10)
    gold_reward: Mapped[int] = mapped_column(default=5)
    skill_bonus: Mapped[str] = mapped_column(String(50))  # Which skill this exercise improves

    def to_dict(self) -> dict:
        """Convert exercise to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.exercise_type,
            "difficulty": self.difficulty,
            "duration_seconds": self.duration_seconds,
            "instructions": self.instructions,
            "xp_reward": self.xp_reward,
            "gold_reward": self.gold_reward,
            "skill_bonus": self.skill_bonus,
        }


class Song(Base):
    """Songs that players learn throughout the game."""

    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(default=1)
    total_segments: Mapped[int] = mapped_column(default=4)
    is_final_song: Mapped[bool] = mapped_column(default=False)

    # Relationships
    segments: Mapped[list["SongSegment"]] = relationship(
        back_populates="song", cascade="all, delete", lazy="selectin"
    )

    def to_dict(self) -> dict:
        """Convert song to dictionary for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "difficulty": self.difficulty,
            "total_segments": self.total_segments,
            "is_final_song": self.is_final_song,
            "segments": [
                seg.to_dict() for seg in sorted(self.segments, key=lambda s: s.segment_index)
            ],
        }


class SongSegment(Base):
    """Segments of a song collected at different locations."""

    __tablename__ = "song_segments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    segment_index: Mapped[int] = mapped_column(default=0)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    unlock_exercise_type: Mapped[str] = mapped_column(String(50), nullable=True)

    # Unique constraint: each song can only have one segment at each index
    __table_args__ = (UniqueConstraint("song_id", "segment_index", name="uix_song_segment"),)

    # Relationships
    song: Mapped["Song"] = relationship(back_populates="segments")
    location: Mapped["Location | None"] = relationship(back_populates="segments")

    def to_dict(self) -> dict:
        """Convert segment to dictionary for API responses."""
        return {
            "id": self.id,
            "song_id": self.song_id,
            "segment_index": self.segment_index,
            "name": self.name,
            "description": self.description,
            "unlock_exercise_type": self.unlock_exercise_type,
            "location_id": self.location_id,
        }


class PlayerProgress(Base):
    """Tracks player progress on exercises, segments, songs, and locations."""

    __tablename__ = "player_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    progress_type: Mapped[str] = mapped_column(String(50))
    reference_id: Mapped[int] = mapped_column()  # ID of exercise/segment/song/location
    state: Mapped[str] = mapped_column(String(50), default=ProgressState.NOT_STARTED.value)
    score: Mapped[int | None] = mapped_column(nullable=True)  # For performance scores
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Unique constraint: one progress entry per player/type/reference combo
    # Index for efficient lookups by player_id, progress_type, reference_id
    __table_args__ = (
        UniqueConstraint("player_id", "progress_type", "reference_id", name="uix_player_progress"),
        Index("ix_player_progress_lookup", "player_id", "progress_type", "reference_id"),
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="progress")

    def to_dict(self) -> dict:
        """Convert progress to dictionary for API responses."""
        return {
            "id": self.id,
            "player_id": self.player_id,
            "progress_type": self.progress_type,
            "reference_id": self.reference_id,
            "state": self.state,
            "score": self.score,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
