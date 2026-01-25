"""Exercise service for business logic."""

from sqlalchemy.orm import Session

from resolute.core.result import Result
from resolute.db.repositories import ExerciseRepository, PlayerRepository, WorldRepository
from resolute.game.exercise_timer import get_exercise_timer
from resolute.game.rewards import RewardCalculator
from resolute.game.services.world import WorldService


class ExerciseService:
    """Business logic for exercise/travel operations."""

    def __init__(self, session: Session):
        self.session = session
        self.player_repo = PlayerRepository(session)
        self.world_repo = WorldRepository(session)
        self.exercise_repo = ExerciseRepository(session)
        self.timer = get_exercise_timer()

    def start_travel(self, player_id: str, destination_id: int) -> Result[dict]:
        """Start travel to a destination (begins exercise timer)."""
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")

        destination = self.world_repo.get_location_by_id(destination_id)
        if destination is None:
            return Result.err("Destination not found")

        # Get a random exercise appropriate for the path
        exercise = self.exercise_repo.get_random(
            exercise_type=destination.exercise_focus,
            min_difficulty=max(1, player.level),
            max_difficulty=player.level + 2,
        )

        if exercise is None:
            exercise = self.exercise_repo.get_random()

        if exercise is None:
            return Result.err("No exercises available")

        # Start exercise timer
        exercise_session = self.timer.start_session(
            player_id=player_id,
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            duration_seconds=exercise.duration_seconds,
            destination_location_id=destination_id,
        )

        return Result.ok({
            "status": "travel_started",
            "exercise": exercise.to_dict(),
            "session": exercise_session.to_dict(),
            "destination": destination.to_dict(include_segments=False),
        })

    def check_exercise(self, player_id: str) -> Result[dict]:
        """Check the status of a player's current exercise."""
        session_status = self.timer.check_session(player_id)
        if session_status is None:
            return Result.err("No active exercise")
        return Result.ok(session_status)

    def complete_exercise(self, player_id: str) -> Result[dict]:
        """Complete an exercise and award rewards."""
        exercise_session = self.timer.get_session(player_id)
        if exercise_session is None:
            return Result.err("No active exercise")

        if not exercise_session.is_complete:
            return Result.err(
                f"Exercise not yet complete. {exercise_session.remaining_seconds:.0f}s remaining"
            )

        # Get the exercise
        exercise = self.exercise_repo.get_by_id(exercise_session.exercise_id)
        if exercise is None:
            return Result.err("Exercise not found")

        player = self.player_repo.get_by_id(player_id)
        if player is None:
            return Result.err("Player not found")

        # Calculate rewards
        reward = RewardCalculator.calculate_exercise_reward(
            exercise=exercise,
            player_level=player.level,
            completion_quality=1.0,
        )

        # Update player stats
        old_level = player.level
        old_xp = player.xp
        player.xp += reward.xp_gained
        player.gold += reward.gold_gained

        if reward.skill_bonus_type:
            player.update_skill(reward.skill_bonus_type, reward.skill_bonus_amount)

        # Check for level up
        leveled_up, new_level = RewardCalculator.check_level_up(old_xp, player.xp)
        if leveled_up:
            player.level = new_level

        # Update location if traveling
        if exercise_session.destination_location_id:
            player.current_location_id = exercise_session.destination_location_id

            # Unlock next location
            world_service = WorldService(self.session)
            world_service.unlock_next_location(player_id)

        self.player_repo.update(player)

        # Complete the timer session
        self.timer.complete_session(player_id)

        # Refresh player after all updates
        player = self.player_repo.get_by_id(player_id)
        reward.level_up = player.level > old_level
        reward.new_level = player.level if reward.level_up else None

        return Result.ok({
            "status": "exercise_completed",
            "rewards": reward.to_dict(),
            "new_location_id": exercise_session.destination_location_id,
            "player": player.to_dict(),
        })
