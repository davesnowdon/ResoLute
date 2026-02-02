"""Player service for business logic."""

import logging

from sqlalchemy.orm import Session

from resolute.core.result import Result
from resolute.db.models import LocationType, Player, SkillType
from resolute.db.repositories import PlayerRepository, ProgressRepository, WorldRepository
from resolute.game.rewards import RewardCalculator

logger = logging.getLogger(__name__)


class PlayerService:
    """Business logic for player operations."""

    def __init__(self, session: Session):
        self.session = session
        self.player_repo = PlayerRepository(session)
        self.world_repo = WorldRepository(session)
        self.progress_repo = ProgressRepository(session)

    def get_or_create(self, player_id: str, name: str | None = None) -> Result[Player]:
        """Get an existing player or create a new one."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            player = self.player_repo.create(player_id, name=name)
            logger.info(f"[{player_id}] New player created")
        return Result.ok(player)

    def get_player(self, player_id: str) -> Result[Player]:
        """Get a player by ID."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found")
            return Result.err("Player not found")
        return Result.ok(player)

    def get_stats(self, player_id: str) -> Result[dict]:
        """Get player stats as a dictionary."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for stats")
            return Result.err("Player not found")
        return Result.ok(player.to_dict())

    def update_stats(
        self,
        player_id: str,
        xp_delta: int = 0,
        gold_delta: int = 0,
        reputation_delta: int = 0,
        skill_type: SkillType | None = None,
        skill_delta: int = 0,
    ) -> Result[Player]:
        """Update player stats and check for level up."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for stat update")
            return Result.err("Player not found")

        old_level = player.level
        old_xp = player.xp
        player.xp += xp_delta
        player.gold += gold_delta
        player.reputation += reputation_delta

        # Update specific skill
        if skill_type and skill_delta:
            player.update_skill(skill_type, skill_delta)

        # Check for level up
        leveled_up, new_level = RewardCalculator.check_level_up(old_xp, player.xp)
        if leveled_up:
            player.level = new_level
            logger.info(f"[{player_id}] Level up! {old_level} -> {new_level}")

        self.player_repo.update(player)
        logger.debug(f"[{player_id}] Stats updated: xp+{xp_delta}, gold+{gold_delta}, rep+{reputation_delta}")
        return Result.ok(player)

    def set_location(self, player_id: str, location_id: int) -> Result[Player]:
        """Set the player's current location."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for location change")
            return Result.err("Player not found")

        player.current_location_id = location_id
        self.player_repo.update(player)
        logger.info(f"[{player_id}] Location changed to location_id={location_id}")
        return Result.ok(player)

    def get_current_location(self, player_id: str) -> Result[dict]:
        """Get the player's current location with available actions."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for current location")
            return Result.err("Player not found")

        if player.current_location_id is None:
            logger.warning(f"[{player_id}] Player has no current location")
            return Result.err("Player has no current location")

        location = self.world_repo.get_location_with_segments(player.current_location_id)
        if location is None:
            logger.warning(f"[{player_id}] Location {player.current_location_id} not found")
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
