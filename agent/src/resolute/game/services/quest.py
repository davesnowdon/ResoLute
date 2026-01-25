"""Quest service for business logic."""

import logging

from sqlalchemy.orm import Session

from resolute.core.result import Result
from resolute.db.models import LocationType, ProgressState, ProgressType
from resolute.db.repositories import PlayerRepository, ProgressRepository, WorldRepository
from resolute.game.rewards import RewardCalculator

logger = logging.getLogger(__name__)


class QuestService:
    """Business logic for segments, performance, and final quest."""

    def __init__(self, session: Session):
        self.session = session
        self.player_repo = PlayerRepository(session)
        self.world_repo = WorldRepository(session)
        self.progress_repo = ProgressRepository(session)

    def collect_segment(self, player_id: str, segment_id: int) -> Result[dict]:
        """Collect a song segment."""
        segment = self.world_repo.get_segment_by_id(segment_id)
        if segment is None:
            logger.warning(f"[{player_id}] Segment {segment_id} not found")
            return Result.err("Segment not found")

        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for segment collection")
            return Result.err("Player not found")

        if segment.location_id != player.current_location_id:
            logger.warning(
                f"[{player_id}] Not at segment location "
                f"(player at {player.current_location_id}, segment at {segment.location_id})"
            )
            return Result.err("You must be at the segment's location to collect it")

        # Check if already collected
        progress = self.progress_repo.get_segment_progress(player_id, segment_id)
        if progress and progress.state == ProgressState.COMPLETED.value:
            logger.warning(f"[{player_id}] Segment {segment_id} already collected")
            return Result.err("Segment already collected")

        # Create or update progress
        if progress is None:
            progress = self.progress_repo.create(
                player_id=player_id,
                progress_type=ProgressType.SEGMENT.value,
                reference_id=segment_id,
            )

        self.progress_repo.mark_completed(progress)
        logger.info(f"[{player_id}] Segment collected: '{segment.name}' (id={segment_id})")

        return Result.ok({
            "status": "segment_collected",
            "segment": segment.to_dict(),
        })

    def get_inventory(self, player_id: str) -> Result[dict]:
        """Get player's collected segments and inventory."""
        collected_segments = self.progress_repo.get_collected_segments(player_id)
        song = self.world_repo.get_default_song()

        total_segments = song.total_segments if song else 4
        song_title = song.title if song else "The Hero's Ballad"

        return Result.ok({
            "collected_segments": [s.to_dict() for s in collected_segments],
            "total_segments": total_segments,
            "song_title": song_title,
            "can_perform_final": len(collected_segments) == total_segments,
        })

    def perform_at_tavern(
        self, player_id: str, performance_score: float = 1.0
    ) -> Result[dict]:
        """Perform at a tavern to earn gold and reputation."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for performance")
            return Result.err("Player not found")

        if player.current_location_id is None:
            logger.warning(f"[{player_id}] No current location for performance")
            return Result.err("You must be at a location")

        location = self.world_repo.get_location_by_id(player.current_location_id)
        if location is None or location.location_type != LocationType.TAVERN.value:
            logger.warning(
                f"[{player_id}] Must be at tavern to perform "
                f"(at location_id={player.current_location_id})"
            )
            return Result.err("You must be at a tavern to perform")

        inventory = self.get_inventory(player_id)
        if inventory.is_err:
            return inventory

        segments_count = len(inventory.unwrap()["collected_segments"])
        song_difficulty = 1 + (segments_count // 2)

        rewards = RewardCalculator.calculate_performance_reward(
            song_difficulty=song_difficulty,
            player_level=player.level,
            performance_score=performance_score,
        )

        player.gold += rewards["gold_gained"]
        player.reputation += rewards["reputation_gained"]
        self.player_repo.update(player)

        # Refresh player after update
        player = self.player_repo.get_by_id(player_id)

        logger.info(
            f"[{player_id}] Tavern performance: "
            f"+{rewards['gold_gained']} gold, +{rewards['reputation_gained']} rep"
        )

        return Result.ok({
            "status": "performance_complete",
            "rewards": rewards,
            "player": player.to_dict(),
        })

    def check_final_quest_ready(self, player_id: str) -> Result[dict]:
        """Check if the player is ready for the final quest."""
        inventory = self.get_inventory(player_id)
        if inventory.is_err:
            return inventory

        inv_data = inventory.unwrap()
        world = self.world_repo.get_by_player_id(player_id)

        collected = len(inv_data["collected_segments"])
        total = inv_data["total_segments"]
        logger.debug(f"[{player_id}] Final quest check: {collected}/{total} segments")

        return Result.ok({
            "ready": inv_data["can_perform_final"],
            "segments_collected": collected,
            "segments_required": total,
            "final_monster": world.final_monster if world else None,
            "rescue_target": world.rescue_target if world else None,
        })

    def complete_final_quest(
        self, player_id: str, performance_score: float = 1.0
    ) -> Result[dict]:
        """Complete the final quest by performing the complete song."""
        ready_check = self.check_final_quest_ready(player_id)
        if ready_check.is_err:
            return ready_check

        ready_data = ready_check.unwrap()
        if not ready_data["ready"]:
            logger.warning(
                f"[{player_id}] Final quest not ready: "
                f"{ready_data['segments_collected']}/{ready_data['segments_required']} segments"
            )
            return Result.err(
                f"Not all segments collected ({ready_data['segments_collected']}/{ready_data['segments_required']})"
            )

        player = self.player_repo.get_by_id(player_id)
        if player is None:
            logger.warning(f"[{player_id}] Player not found for final quest")
            return Result.err("Player not found")

        world = self.world_repo.get_by_player_id(player_id)
        if world is None:
            logger.warning(f"[{player_id}] World not found for final quest")
            return Result.err("World not found")

        rewards = RewardCalculator.calculate_final_quest_reward(
            player_level=player.level,
            segments_collected=ready_data["segments_collected"],
            performance_score=performance_score,
        )

        if rewards["victory"]:
            player.xp += rewards["xp_gained"]
            player.gold += rewards["gold_gained"]
            player.reputation += rewards["reputation_gained"]
            self.player_repo.update(player)

        # Refresh player after update
        player = self.player_repo.get_by_id(player_id)

        logger.info(
            f"[{player_id}] Final quest {'VICTORY' if rewards['victory'] else 'FAILED'}: "
            f"monster={world.final_monster}, xp+{rewards['xp_gained']}, gold+{rewards['gold_gained']}"
        )

        return Result.ok({
            "status": "game_complete" if rewards["victory"] else "quest_failed",
            "victory": rewards["victory"],
            "monster_charmed": world.final_monster,
            "rescued": world.rescue_target if rewards["victory"] else None,
            "rewards": rewards,
            "player": player.to_dict(),
        })
