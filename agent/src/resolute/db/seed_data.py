"""Seed data for pre-defined exercises and songs."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from resolute.db.models import Exercise, ExerciseType, Song, SongSegment

# Pre-defined exercises library
EXERCISES = [
    # Rhythm exercises (warm-up, travel)
    {
        "name": "Steady Beat March",
        "exercise_type": ExerciseType.RHYTHM.value,
        "difficulty": 1,
        "duration_seconds": 30,
        "instructions": "Tap along to a steady beat. Keep the tempo even as you march in place.",
        "xp_reward": 10,
        "gold_reward": 5,
        "skill_bonus": "rhythm",
    },
    {
        "name": "Clap and Count",
        "exercise_type": ExerciseType.RHYTHM.value,
        "difficulty": 2,
        "duration_seconds": 45,
        "instructions": "Clap on beats 1 and 3 while counting 1-2-3-4 out loud.",
        "xp_reward": 15,
        "gold_reward": 8,
        "skill_bonus": "rhythm",
    },
    {
        "name": "Syncopation Challenge",
        "exercise_type": ExerciseType.RHYTHM.value,
        "difficulty": 4,
        "duration_seconds": 60,
        "instructions": "Clap on the off-beats (the 'and' of each count). Feel the groove!",
        "xp_reward": 25,
        "gold_reward": 12,
        "skill_bonus": "rhythm",
    },
    {
        "name": "Polyrhythm Practice",
        "exercise_type": ExerciseType.RHYTHM.value,
        "difficulty": 6,
        "duration_seconds": 90,
        "instructions": "Tap 3 beats with your right hand while tapping 2 beats with your left.",
        "xp_reward": 40,
        "gold_reward": 20,
        "skill_bonus": "rhythm",
    },
    # Melody exercises
    {
        "name": "Scale Ascent",
        "exercise_type": ExerciseType.MELODY.value,
        "difficulty": 1,
        "duration_seconds": 30,
        "instructions": "Sing or hum a major scale going up: Do-Re-Mi-Fa-Sol-La-Ti-Do.",
        "xp_reward": 10,
        "gold_reward": 5,
        "skill_bonus": "melody",
    },
    {
        "name": "Interval Jumps",
        "exercise_type": ExerciseType.MELODY.value,
        "difficulty": 3,
        "duration_seconds": 60,
        "instructions": "Practice singing intervals: start on any note, jump up a third, then a fifth.",
        "xp_reward": 20,
        "gold_reward": 10,
        "skill_bonus": "melody",
    },
    {
        "name": "Melodic Contour",
        "exercise_type": ExerciseType.MELODY.value,
        "difficulty": 4,
        "duration_seconds": 60,
        "instructions": "Listen to a short melody and trace its shape in the air with your finger.",
        "xp_reward": 25,
        "gold_reward": 12,
        "skill_bonus": "melody",
    },
    {
        "name": "Improvisation Journey",
        "exercise_type": ExerciseType.MELODY.value,
        "difficulty": 7,
        "duration_seconds": 120,
        "instructions": "Create your own melody using only 5 notes (pentatonic scale). Let it flow!",
        "xp_reward": 50,
        "gold_reward": 25,
        "skill_bonus": "melody",
    },
    # Harmony exercises
    {
        "name": "Chord Recognition",
        "exercise_type": ExerciseType.HARMONY.value,
        "difficulty": 2,
        "duration_seconds": 45,
        "instructions": "Listen to chords and identify if they are major (happy) or minor (sad).",
        "xp_reward": 15,
        "gold_reward": 8,
        "skill_bonus": "harmony",
    },
    {
        "name": "Root Note Hunt",
        "exercise_type": ExerciseType.HARMONY.value,
        "difficulty": 3,
        "duration_seconds": 60,
        "instructions": "When you hear a chord, try to sing or hum the lowest note (the root).",
        "xp_reward": 20,
        "gold_reward": 10,
        "skill_bonus": "harmony",
    },
    {
        "name": "Chord Progressions",
        "exercise_type": ExerciseType.HARMONY.value,
        "difficulty": 5,
        "duration_seconds": 90,
        "instructions": "Listen to a I-IV-V-I progression. Feel how the chords want to resolve home.",
        "xp_reward": 35,
        "gold_reward": 18,
        "skill_bonus": "harmony",
    },
    {
        "name": "Voice Leading",
        "exercise_type": ExerciseType.HARMONY.value,
        "difficulty": 8,
        "duration_seconds": 120,
        "instructions": "Sing the top note of each chord as they change. Keep your voice moving smoothly.",
        "xp_reward": 60,
        "gold_reward": 30,
        "skill_bonus": "harmony",
    },
    # Ear training exercises
    {
        "name": "Note Matching",
        "exercise_type": ExerciseType.EAR_TRAINING.value,
        "difficulty": 1,
        "duration_seconds": 30,
        "instructions": "Listen to a note and try to match it with your voice. Hold it steady.",
        "xp_reward": 10,
        "gold_reward": 5,
        "skill_bonus": "melody",
    },
    {
        "name": "Interval Identification",
        "exercise_type": ExerciseType.EAR_TRAINING.value,
        "difficulty": 4,
        "duration_seconds": 60,
        "instructions": "Listen to two notes and identify the interval between them.",
        "xp_reward": 25,
        "gold_reward": 12,
        "skill_bonus": "melody",
    },
    {
        "name": "Melody Memory",
        "exercise_type": ExerciseType.EAR_TRAINING.value,
        "difficulty": 5,
        "duration_seconds": 90,
        "instructions": "Listen to a 4-note melody, then sing it back from memory.",
        "xp_reward": 35,
        "gold_reward": 18,
        "skill_bonus": "melody",
    },
    # Sight reading exercises
    {
        "name": "Note Names",
        "exercise_type": ExerciseType.SIGHT_READING.value,
        "difficulty": 1,
        "duration_seconds": 30,
        "instructions": "Look at notes on the staff and say their letter names out loud.",
        "xp_reward": 10,
        "gold_reward": 5,
        "skill_bonus": "melody",
    },
    {
        "name": "Rhythm Reading",
        "exercise_type": ExerciseType.SIGHT_READING.value,
        "difficulty": 3,
        "duration_seconds": 60,
        "instructions": "Clap the rhythm you see on the page. Watch for quarter and eighth notes.",
        "xp_reward": 20,
        "gold_reward": 10,
        "skill_bonus": "rhythm",
    },
]

# The default song for the adventure
DEFAULT_SONG = {
    "title": "The Hero's Ballad",
    "description": "A legendary song passed down through generations, said to have the power to charm even the fiercest monsters.",
    "difficulty": 3,
    "total_segments": 4,
    "is_final_song": True,
    "segments": [
        {
            "segment_index": 0,
            "name": "The Opening Verse",
            "description": "A gentle introduction that speaks of a hero's humble beginnings.",
            "unlock_exercise_type": ExerciseType.MELODY.value,
        },
        {
            "segment_index": 1,
            "name": "The Rising Chorus",
            "description": "The melody builds as the hero faces their first challenge.",
            "unlock_exercise_type": ExerciseType.RHYTHM.value,
        },
        {
            "segment_index": 2,
            "name": "The Bridge of Trials",
            "description": "A complex passage representing the hero's darkest hour.",
            "unlock_exercise_type": ExerciseType.HARMONY.value,
        },
        {
            "segment_index": 3,
            "name": "The Final Refrain",
            "description": "A triumphant conclusion that brings all elements together.",
            "unlock_exercise_type": ExerciseType.EAR_TRAINING.value,
        },
    ],
}


async def seed_exercises_and_songs(session: AsyncSession) -> None:
    """Seed the database with pre-defined exercises and the default song."""
    # Check if exercises already exist
    result = await session.execute(select(Exercise).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # Already seeded

    # Add exercises
    for exercise_data in EXERCISES:
        exercise = Exercise(**exercise_data)
        session.add(exercise)

    # Add the default song with segments
    song_data = DEFAULT_SONG.copy()
    segments_data = song_data.pop("segments")
    song = Song(**song_data)
    session.add(song)
    await session.flush()  # Get the song ID

    # Add segments
    for segment_data in segments_data:
        segment = SongSegment(song_id=song.id, **segment_data)
        session.add(segment)

    await session.commit()


async def get_exercises_by_type(
    session: AsyncSession, exercise_type: str, max_difficulty: int = 10
) -> list[Exercise]:
    """Get exercises filtered by type and difficulty."""
    result = await session.execute(
        select(Exercise)
        .where(Exercise.exercise_type == exercise_type)
        .where(Exercise.difficulty <= max_difficulty)
        .order_by(Exercise.difficulty)
    )
    return list(result.scalars().all())


async def get_random_exercise(
    session: AsyncSession, exercise_type: str | None = None, difficulty: int | None = None
) -> Exercise | None:
    """Get a random exercise, optionally filtered by type and difficulty."""
    from sqlalchemy import func

    query = select(Exercise)
    if exercise_type:
        query = query.where(Exercise.exercise_type == exercise_type)
    if difficulty:
        # Allow +/- 1 difficulty variance
        query = query.where(Exercise.difficulty >= difficulty - 1)
        query = query.where(Exercise.difficulty <= difficulty + 1)

    query = query.order_by(func.random()).limit(1)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_default_song(session: AsyncSession) -> Song | None:
    """Get the default final song."""
    result = await session.execute(select(Song).where(Song.is_final_song.is_(True)).limit(1))
    return result.scalar_one_or_none()


# Synchronous versions for use in greenlet contexts (LangGraph tools)


def get_random_exercise_sync(
    session: Session, exercise_type: str | None = None, difficulty: int | None = None
) -> Exercise | None:
    """Get a random exercise (sync version for greenlet contexts)."""
    query = select(Exercise)
    if exercise_type:
        query = query.where(Exercise.exercise_type == exercise_type)
    if difficulty:
        query = query.where(Exercise.difficulty >= difficulty - 1)
        query = query.where(Exercise.difficulty <= difficulty + 1)

    query = query.order_by(func.random()).limit(1)
    result = session.execute(query)
    return result.scalar_one_or_none()


def get_default_song_sync(session: Session) -> Song | None:
    """Get the default final song (sync version for greenlet contexts)."""
    result = session.execute(select(Song).where(Song.is_final_song.is_(True)).limit(1))
    return result.scalar_one_or_none()


if __name__ == "__main__":
    import asyncio

    from resolute.db.session import create_tables, get_async_session

    async def main():
        await create_tables()
        async with get_async_session() as session:
            await seed_exercises_and_songs(session)
            print("Database seeded successfully!")

            # Verify
            result = await session.execute(select(Exercise))
            exercises = result.scalars().all()
            print(f"Created {len(exercises)} exercises")

            result = await session.execute(select(Song))
            songs = result.scalars().all()
            print(f"Created {len(songs)} songs")

    asyncio.run(main())
