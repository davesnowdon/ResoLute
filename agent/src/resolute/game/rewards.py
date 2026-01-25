"""Reward calculations for exercises and performances."""

from dataclasses import dataclass

from resolute.db.models import Exercise, SkillType


@dataclass
class RewardResult:
    """Result of a reward calculation."""

    xp_gained: int
    gold_gained: int
    skill_bonus_type: SkillType | None
    skill_bonus_amount: int
    level_up: bool = False
    new_level: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "xp_gained": self.xp_gained,
            "gold_gained": self.gold_gained,
            "skill_bonus_type": self.skill_bonus_type.value if self.skill_bonus_type else None,
            "skill_bonus_amount": self.skill_bonus_amount,
            "level_up": self.level_up,
            "new_level": self.new_level,
        }


class RewardCalculator:
    """Calculates rewards for various game activities."""

    # XP required for each level (level -> total XP needed)
    LEVEL_XP_REQUIREMENTS = {
        1: 0,
        2: 100,
        3: 250,
        4: 500,
        5: 850,
        6: 1300,
        7: 1850,
        8: 2500,
        9: 3250,
        10: 4100,
    }

    # Skill bonus per exercise difficulty
    SKILL_BONUS_BASE = 2
    SKILL_BONUS_PER_DIFFICULTY = 1

    # Performance multipliers
    TAVERN_GOLD_MULTIPLIER = 2
    TAVERN_REPUTATION_BASE = 5

    @classmethod
    def calculate_exercise_reward(
        cls,
        exercise: Exercise,
        player_level: int,
        completion_quality: float = 1.0,  # 0.0 - 1.0 scale
    ) -> RewardResult:
        """Calculate rewards for completing an exercise."""
        # Base rewards from exercise
        xp_gained = int(exercise.xp_reward * completion_quality)
        gold_gained = int(exercise.gold_reward * completion_quality)

        # Skill bonus scales with difficulty
        skill_bonus = cls.SKILL_BONUS_BASE + (exercise.difficulty * cls.SKILL_BONUS_PER_DIFFICULTY)
        skill_bonus = int(skill_bonus * completion_quality)

        return RewardResult(
            xp_gained=xp_gained,
            gold_gained=gold_gained,
            skill_bonus_type=SkillType(exercise.skill_bonus) if exercise.skill_bonus else None,
            skill_bonus_amount=skill_bonus,
        )

    @classmethod
    def calculate_level(cls, total_xp: int) -> int:
        """Calculate player level from total XP."""
        level = 1
        for lvl, xp_required in sorted(cls.LEVEL_XP_REQUIREMENTS.items()):
            if total_xp >= xp_required:
                level = lvl
            else:
                break
        return level

    @classmethod
    def xp_for_next_level(cls, current_level: int) -> int | None:
        """Get XP required for the next level."""
        next_level = current_level + 1
        return cls.LEVEL_XP_REQUIREMENTS.get(next_level)

    @classmethod
    def check_level_up(cls, old_xp: int, new_xp: int) -> tuple[bool, int]:
        """Check if the player leveled up and return the new level."""
        old_level = cls.calculate_level(old_xp)
        new_level = cls.calculate_level(new_xp)
        return new_level > old_level, new_level

    @classmethod
    def calculate_performance_reward(
        cls,
        song_difficulty: int,
        player_level: int,
        performance_score: float = 1.0,  # 0.0 - 1.0 scale
    ) -> dict:
        """Calculate rewards for a tavern performance."""
        base_gold = 10 * song_difficulty
        gold_gained = int(base_gold * cls.TAVERN_GOLD_MULTIPLIER * performance_score)

        reputation_gained = int(cls.TAVERN_REPUTATION_BASE * song_difficulty * performance_score)

        return {
            "gold_gained": gold_gained,
            "reputation_gained": reputation_gained,
            "performance_score": round(performance_score * 100),
        }

    @classmethod
    def calculate_final_quest_reward(
        cls,
        player_level: int,
        segments_collected: int,
        performance_score: float = 1.0,
    ) -> dict:
        """Calculate rewards for completing the final quest."""
        base_xp = 500
        base_gold = 200
        base_reputation = 100

        # Bonus for collecting all segments
        segment_multiplier = min(1.5, 0.8 + (segments_collected * 0.175))

        xp_gained = int(base_xp * segment_multiplier * performance_score)
        gold_gained = int(base_gold * segment_multiplier * performance_score)
        reputation_gained = int(base_reputation * segment_multiplier * performance_score)

        return {
            "xp_gained": xp_gained,
            "gold_gained": gold_gained,
            "reputation_gained": reputation_gained,
            "segments_used": segments_collected,
            "performance_score": round(performance_score * 100),
            "victory": performance_score >= 0.5,  # Need at least 50% to win
        }
