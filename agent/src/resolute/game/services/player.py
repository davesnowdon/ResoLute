"""Player service for business logic."""

from sqlalchemy.orm import Session

from resolute.core.result import Result
from resolute.db.models import LocationType, Player
from resolute.db.repositories import PlayerRepository, ProgressRepository, WorldRepository
from resolute.game.rewards import RewardCalculator


class PlayerService:
    """Business logic for player operations."""

    def __init__(self, session: Session):
        self.session = session
        self.player_repo = PlayerRepository(session)
        self.world_repo = WorldRepository(session)
        self.progress_repo = ProgressRepository(session)

    def get_or_create(self, player_id: str) -> Result[Player]:
        """Get an existing player or create a new one."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            player = self.player_repo.create(player_id)
        return Result.ok(player)

    def get_player(self, player_id: str) -> Result[Player]:
        """Get a player by ID."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")
        return Result.ok(player)

    def get_stats(self, player_id: str) -> Result[dict]:
        """Get player stats as a dictionary."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")
        return Result.ok(player.to_dict())

    def update_stats(
        self,
        player_id: str,
        xp_delta: int = 0,
        gold_delta: int = 0,
        reputation_delta: int = 0,
        skill_type: str | None = None,
        skill_delta: int = 0,
    ) -> Result[Player]:
        """Update player stats and check for level up."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")

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

        self.player_repo.update(player)
        return Result.ok(player)

    def set_location(self, player_id: str, location_id: int) -> Result[Player]:
        """Set the player's current location."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")

        player.current_location_id = location_id
        self.player_repo.update(player)
        return Result.ok(player)

    def get_current_location(self, player_id: str) -> Result[dict]:
        """Get the player's current location with available actions."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")

        if player.current_location_id is None:
            return Result.err("Player has no current location")

        location = self.world_repo.get_location_with_segments(player.current_location_id)
        if location is None:
            return Result.err("Location not found")

        # Get available destinations
        destinations = self.world_repo.get_unlocked_destinations(
            location.world_id, location.id
        )

        # Also include the next locked location (allows progression)
        next_locked = self.world_repo.get_next_locked_location(location.world_id)
        if next_locked and next_locked.id != location.id:
            destinations.append(next_locked)

        # Check for uncollected segments
        collected_ids = self.progress_repo.get_collected_segment_ids(player_id)
        uncollected_segments = [
            segment.to_dict()
            for segment in location.segments
            if segment.id not in collected_ids
        ]

        return Result.ok({
            "location": location.to_dict(),
            "available_destinations": [
                d.to_dict(include_segments=False) for d in destinations
            ],
            "uncollected_segments": uncollected_segments,
            "can_travel": len(destinations) > 0,
            "has_tavern": location.location_type == LocationType.TAVERN.value,
        })
