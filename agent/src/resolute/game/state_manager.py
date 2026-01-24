"""Central game state manager for ResoLute.

All database operations are synchronous to avoid greenlet/async boundary issues
when tools are invoked by LangGraph's ReAct agent.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from resolute.db.models import (
    Exercise,
    Location,
    LocationType,
    Player,
    PlayerProgress,
    ProgressState,
    ProgressType,
    Song,
    SongSegment,
    World,
)
from resolute.game.exercise_timer import ExerciseTimer, get_exercise_timer
from resolute.game.rewards import RewardCalculator


class GameStateManager:
    """Central manager for all game state operations.

    Uses synchronous database operations to work correctly in all contexts,
    including LangGraph tool invocations.
    """

    def __init__(self, session: Session):
        self._session = session
        self._timer = get_exercise_timer()

    @property
    def timer(self) -> ExerciseTimer:
        """Get the exercise timer."""
        return self._timer

    # Player Management

    def get_or_create_player(self, player_id: str) -> Player:
        """Get an existing player or create a new one."""
        result = self._session.execute(select(Player).where(Player.id == player_id))
        player = result.scalar_one_or_none()

        if player is None:
            player = Player(id=player_id, name=f"Bard {player_id[:8]}")
            self._session.add(player)
            self._session.flush()

        return player

    def get_player(self, player_id: str) -> Player | None:
        """Get a player by ID."""
        result = self._session.execute(select(Player).where(Player.id == player_id))
        return result.scalar_one_or_none()

    def get_player_stats(self, player_id: str) -> dict | None:
        """Get player stats as a dictionary."""
        player = self.get_player(player_id)
        if player is None:
            return None
        return player.to_dict()

    def update_player_stats(
        self,
        player_id: str,
        xp_delta: int = 0,
        gold_delta: int = 0,
        reputation_delta: int = 0,
        skill_type: str | None = None,
        skill_delta: int = 0,
    ) -> Player | None:
        """Update player stats and check for level up."""
        player = self.get_player(player_id)
        if player is None:
            return None

        old_xp = player.xp
        player.xp += xp_delta
        player.gold += gold_delta
        player.reputation += reputation_delta

        # Update specific skill
        if skill_type and skill_delta:
            if skill_type == "rhythm":
                player.skill_rhythm = min(100, player.skill_rhythm + skill_delta)
            elif skill_type == "melody":
                player.skill_melody = min(100, player.skill_melody + skill_delta)
            elif skill_type == "harmony":
                player.skill_harmony = min(100, player.skill_harmony + skill_delta)

        # Check for level up
        leveled_up, new_level = RewardCalculator.check_level_up(old_xp, player.xp)
        if leveled_up:
            player.level = new_level

        self._session.flush()
        return player

    # World Management

    def get_player_world(self, player_id: str) -> World | None:
        """Get the player's world with all locations."""
        result = self._session.execute(
            select(World)
            .where(World.player_id == player_id)
            .options(selectinload(World.locations).selectinload(Location.segments))
        )
        return result.scalar_one_or_none()

    def get_or_generate_world(self, player_id: str) -> dict:
        """Get player's world or trigger generation if none exists."""
        world = self.get_player_world(player_id)
        if world is None:
            return {"needs_generation": True, "player_id": player_id}
        return {"needs_generation": False, "world": world.to_dict()}

    def create_world(
        self,
        player_id: str,
        name: str,
        theme: str,
        story_arc: str,
        final_monster: str,
        rescue_target: str,
        locations: list[dict],
    ) -> World:
        """Create a new world for a player with locations."""
        # Ensure player exists
        player = self.get_or_create_player(player_id)

        # Create world
        world = World(
            player_id=player_id,
            name=name,
            theme=theme,
            story_arc=story_arc,
            final_monster=final_monster,
            rescue_target=rescue_target,
        )
        self._session.add(world)
        self._session.flush()

        # Create locations
        for i, loc_data in enumerate(locations):
            location = Location(
                world_id=world.id,
                name=loc_data["name"],
                description=loc_data.get("description", ""),
                location_type=loc_data.get("type", LocationType.VILLAGE.value),
                exercise_focus=loc_data.get("exercise_focus"),
                order_index=i,
                is_unlocked=i == 0,  # First location is unlocked
            )
            self._session.add(location)

        self._session.flush()

        # Get the default song and distribute segments across locations
        self._distribute_song_segments(world.id)

        # Set player's starting location
        first_location = self._get_first_location(world.id)
        if first_location:
            player.current_location_id = first_location.id
            self._session.flush()

        # Reload world with all relationships
        return self.get_player_world(player_id)

    def _distribute_song_segments(self, world_id: int) -> None:
        """Distribute song segments across world locations."""
        # Get the default song
        song = self._get_default_song()
        if song is None:
            return

        # Get world locations (excluding the dungeon which is the final destination)
        result = self._session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .where(Location.location_type != LocationType.DUNGEON.value)
            .order_by(Location.order_index)
        )
        locations = list(result.scalars().all())

        # Get song segments
        result = self._session.execute(
            select(SongSegment)
            .where(SongSegment.song_id == song.id)
            .order_by(SongSegment.segment_index)
        )
        segments = list(result.scalars().all())

        # Assign segments to locations
        for i, segment in enumerate(segments):
            if i < len(locations):
                segment.location_id = locations[i].id

        self._session.flush()

    def _get_first_location(self, world_id: int) -> Location | None:
        """Get the first location in a world."""
        result = self._session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .order_by(Location.order_index)
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _get_default_song(self) -> Song | None:
        """Get the default final song."""
        result = self._session.execute(
            select(Song).where(Song.is_final_song.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()

    def _get_random_exercise(
        self, exercise_type: str | None = None, difficulty: int | None = None
    ) -> Exercise | None:
        """Get a random exercise, optionally filtered by type and difficulty."""
        from sqlalchemy import func

        query = select(Exercise)
        if exercise_type:
            query = query.where(Exercise.exercise_type == exercise_type)
        if difficulty:
            query = query.where(Exercise.difficulty >= difficulty - 1)
            query = query.where(Exercise.difficulty <= difficulty + 1)

        query = query.order_by(func.random()).limit(1)
        result = self._session.execute(query)
        return result.scalar_one_or_none()

    # Location Management

    def get_current_location(self, player_id: str) -> dict | None:
        """Get the player's current location with available actions."""
        player = self.get_player(player_id)
        if player is None or player.current_location_id is None:
            return None

        result = self._session.execute(
            select(Location)
            .where(Location.id == player.current_location_id)
            .options(selectinload(Location.segments))
        )
        location = result.scalar_one_or_none()
        if location is None:
            return None

        # Get available destinations (unlocked locations + next locked location)
        result = self._session.execute(
            select(Location)
            .where(Location.world_id == location.world_id)
            .where(Location.is_unlocked.is_(True))
            .where(Location.id != location.id)
            .order_by(Location.order_index)
        )
        destinations = list(result.scalars().all())

        # Also include the next locked location (allows progression)
        result = self._session.execute(
            select(Location)
            .where(Location.world_id == location.world_id)
            .where(Location.is_unlocked.is_(False))
            .order_by(Location.order_index)
            .limit(1)
        )
        next_locked = result.scalar_one_or_none()
        if next_locked and next_locked.id != location.id:
            destinations.append(next_locked)

        # Check for uncollected segments using batch query
        segment_ids = [s.id for s in location.segments]
        if segment_ids:
            result = self._session.execute(
                select(PlayerProgress.reference_id)
                .where(PlayerProgress.player_id == player_id)
                .where(PlayerProgress.progress_type == ProgressType.SEGMENT.value)
                .where(PlayerProgress.reference_id.in_(segment_ids))
                .where(PlayerProgress.state == ProgressState.COMPLETED.value)
            )
            collected_ids = {row[0] for row in result.all()}
        else:
            collected_ids = set()

        uncollected_segments = [
            segment.to_dict()
            for segment in location.segments
            if segment.id not in collected_ids
        ]

        return {
            "location": location.to_dict(),
            "available_destinations": [
                d.to_dict(include_segments=False) for d in destinations
            ],
            "uncollected_segments": uncollected_segments,
            "can_travel": len(destinations) > 0,
            "has_tavern": location.location_type == LocationType.TAVERN.value,
        }

    def get_location_by_id(self, location_id: int) -> Location | None:
        """Get a location by ID."""
        result = self._session.execute(
            select(Location).where(Location.id == location_id)
        )
        return result.scalar_one_or_none()

    # Travel & Exercise

    def start_travel(self, player_id: str, destination_id: int) -> dict[str, Any]:
        """Start travel to a destination (begins exercise timer)."""
        player = self.get_player(player_id)
        if player is None:
            return {"error": "Player not found"}

        destination = self.get_location_by_id(destination_id)
        if destination is None:
            return {"error": "Destination not found"}

        # Get a random exercise appropriate for the path
        exercise = self._get_random_exercise(
            exercise_type=destination.exercise_focus,
            difficulty=player.level + 1,
        )

        if exercise is None:
            exercise = self._get_random_exercise()

        if exercise is None:
            return {"error": "No exercises available"}

        # Start exercise timer
        exercise_session = self._timer.start_session(
            player_id=player_id,
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            duration_seconds=exercise.duration_seconds,
            destination_location_id=destination_id,
        )

        return {
            "status": "travel_started",
            "exercise": exercise.to_dict(),
            "session": exercise_session.to_dict(),
            "destination": destination.to_dict(include_segments=False),
        }

    def check_exercise(self, player_id: str) -> dict | None:
        """Check the status of a player's current exercise."""
        return self._timer.check_session(player_id)

    def complete_exercise(self, player_id: str) -> dict[str, Any]:
        """Complete an exercise and award rewards."""
        exercise_session = self._timer.get_session(player_id)
        if exercise_session is None:
            return {"error": "No active exercise"}

        if not exercise_session.is_complete:
            return {
                "error": "Exercise not yet complete",
                "remaining_seconds": exercise_session.remaining_seconds,
            }

        # Get the exercise
        result = self._session.execute(
            select(Exercise).where(Exercise.id == exercise_session.exercise_id)
        )
        exercise = result.scalar_one_or_none()
        if exercise is None:
            return {"error": "Exercise not found"}

        player = self.get_player(player_id)
        if player is None:
            return {"error": "Player not found"}

        # Calculate rewards
        reward = RewardCalculator.calculate_exercise_reward(
            exercise=exercise,
            player_level=player.level,
            completion_quality=1.0,
        )

        # Update player stats
        old_level = player.level
        self.update_player_stats(
            player_id=player_id,
            xp_delta=reward.xp_gained,
            gold_delta=reward.gold_gained,
            skill_type=reward.skill_bonus_type,
            skill_delta=reward.skill_bonus_amount,
        )

        # Update location if traveling
        if exercise_session.destination_location_id:
            player.current_location_id = exercise_session.destination_location_id
            self._unlock_next_location(player_id)
            self._session.flush()

        # Complete the session
        self._timer.complete_session(player_id)

        # Check for level up
        player = self.get_player(player_id)
        reward.level_up = player.level > old_level
        reward.new_level = player.level if reward.level_up else None

        return {
            "status": "exercise_completed",
            "rewards": reward.to_dict(),
            "new_location_id": exercise_session.destination_location_id,
            "player": player.to_dict(),
        }

    def _unlock_next_location(self, player_id: str) -> None:
        """Unlock the next location in sequence."""
        world = self.get_player_world(player_id)
        if world is None:
            return

        for location in sorted(world.locations, key=lambda x: x.order_index):
            if not location.is_unlocked:
                location.is_unlocked = True
                self._session.flush()
                break

    # Song Segments

    def collect_segment(self, player_id: str, segment_id: int) -> dict[str, Any]:
        """Collect a song segment."""
        result = self._session.execute(
            select(SongSegment).where(SongSegment.id == segment_id)
        )
        segment = result.scalar_one_or_none()
        if segment is None:
            return {"error": "Segment not found"}

        player = self.get_player(player_id)
        if player is None:
            return {"error": "Player not found"}

        if segment.location_id != player.current_location_id:
            return {"error": "You must be at the segment's location to collect it"}

        # Check if already collected
        progress = self._get_progress(player_id, ProgressType.SEGMENT.value, segment_id)
        if progress and progress.state == ProgressState.COMPLETED.value:
            return {"error": "Segment already collected"}

        # Create or update progress
        if progress is None:
            progress = PlayerProgress(
                player_id=player_id,
                progress_type=ProgressType.SEGMENT.value,
                reference_id=segment_id,
            )
            self._session.add(progress)

        progress.state = ProgressState.COMPLETED.value
        progress.completed_at = datetime.utcnow()
        self._session.flush()

        return {
            "status": "segment_collected",
            "segment": segment.to_dict(),
        }

    def _get_progress(
        self, player_id: str, progress_type: str, reference_id: int
    ) -> PlayerProgress | None:
        """Get a specific progress entry."""
        result = self._session.execute(
            select(PlayerProgress)
            .where(PlayerProgress.player_id == player_id)
            .where(PlayerProgress.progress_type == progress_type)
            .where(PlayerProgress.reference_id == reference_id)
        )
        return result.scalar_one_or_none()

    def get_inventory(self, player_id: str) -> dict[str, Any]:
        """Get player's collected segments and inventory."""
        result = self._session.execute(
            select(PlayerProgress)
            .where(PlayerProgress.player_id == player_id)
            .where(PlayerProgress.progress_type == ProgressType.SEGMENT.value)
            .where(PlayerProgress.state == ProgressState.COMPLETED.value)
        )
        segment_progress = list(result.scalars().all())

        collected_segments = []
        for progress in segment_progress:
            result = self._session.execute(
                select(SongSegment).where(SongSegment.id == progress.reference_id)
            )
            segment = result.scalar_one_or_none()
            if segment:
                collected_segments.append(segment.to_dict())

        song = self._get_default_song()

        return {
            "collected_segments": collected_segments,
            "total_segments": song.total_segments if song else 4,
            "song_title": song.title if song else "The Hero's Ballad",
            "can_perform_final": len(collected_segments)
            == (song.total_segments if song else 4),
        }

    # Performance

    def perform_at_tavern(
        self, player_id: str, performance_score: float = 1.0
    ) -> dict[str, Any]:
        """Perform at a tavern to earn gold and reputation."""
        player = self.get_player(player_id)
        if player is None:
            return {"error": "Player not found"}

        if player.current_location_id is None:
            return {"error": "You must be at a location"}

        location = self.get_location_by_id(player.current_location_id)
        if location is None or location.location_type != LocationType.TAVERN.value:
            return {"error": "You must be at a tavern to perform"}

        inventory = self.get_inventory(player_id)
        segments_count = len(inventory["collected_segments"])
        song_difficulty = 1 + (segments_count // 2)

        rewards = RewardCalculator.calculate_performance_reward(
            song_difficulty=song_difficulty,
            player_level=player.level,
            performance_score=performance_score,
        )

        self.update_player_stats(
            player_id=player_id,
            gold_delta=rewards["gold_gained"],
            reputation_delta=rewards["reputation_gained"],
        )

        player = self.get_player(player_id)

        return {
            "status": "performance_complete",
            "rewards": rewards,
            "player": player.to_dict(),
        }

    def check_final_quest_ready(self, player_id: str) -> dict[str, Any]:
        """Check if the player is ready for the final quest."""
        inventory = self.get_inventory(player_id)
        world = self.get_player_world(player_id)

        return {
            "ready": inventory["can_perform_final"],
            "segments_collected": len(inventory["collected_segments"]),
            "segments_required": inventory["total_segments"],
            "final_monster": world.final_monster if world else None,
            "rescue_target": world.rescue_target if world else None,
        }

    def complete_final_quest(
        self, player_id: str, performance_score: float = 1.0
    ) -> dict[str, Any]:
        """Complete the final quest by performing the complete song."""
        ready_check = self.check_final_quest_ready(player_id)
        if not ready_check["ready"]:
            return {
                "error": "Not all segments collected",
                "segments_collected": ready_check["segments_collected"],
                "segments_required": ready_check["segments_required"],
            }

        player = self.get_player(player_id)
        if player is None:
            return {"error": "Player not found"}

        world = self.get_player_world(player_id)
        if world is None:
            return {"error": "World not found"}

        rewards = RewardCalculator.calculate_final_quest_reward(
            player_level=player.level,
            segments_collected=ready_check["segments_collected"],
            performance_score=performance_score,
        )

        if rewards["victory"]:
            self.update_player_stats(
                player_id=player_id,
                xp_delta=rewards["xp_gained"],
                gold_delta=rewards["gold_gained"],
                reputation_delta=rewards["reputation_gained"],
            )

        player = self.get_player(player_id)

        return {
            "status": "game_complete" if rewards["victory"] else "quest_failed",
            "victory": rewards["victory"],
            "monster_charmed": world.final_monster,
            "rescued": world.rescue_target if rewards["victory"] else None,
            "rewards": rewards,
            "player": player.to_dict(),
        }
