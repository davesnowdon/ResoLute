"""AI-powered world generation for ResoLute."""

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from resolute.agent.prompts import WORLD_GENERATION_PROMPT
from resolute.db.models import ExerciseType, LocationType

logger = logging.getLogger(__name__)


class LocationSchema(BaseModel):
    """Schema for a world location."""

    name: str = Field(description="Name of the location")
    description: str = Field(description="Brief location description")
    type: str = Field(default="village", description="village|tavern|path|dungeon")
    exercise_focus: str = Field(
        description="rhythm|melody|harmony|ear_training|sight_reading"
    )


class WorldSchema(BaseModel):
    """Schema for AI-generated world data."""

    name: str = Field(description="Name of the World")
    theme: str = Field(description="Brief theme description")
    story_arc: str = Field(description="2-3 sentence story about the quest")
    final_monster: str = Field(description="Name of the monster")
    rescue_target: str = Field(description="Who needs to be rescued")
    locations: list[LocationSchema] = Field(description="List of 4-5 locations")


class WorldGenerator:
    """Generates unique fantasy worlds using AI."""

    def __init__(
        self,
        model: str,
        tracer: object | None = None,
    ):
        logger.info("WorldGenerator.__init__ starting...")
        logger.info(f"Creating chat model: {model}")
        from resolute.llm import create_chat_model

        self._model = create_chat_model(model, temperature=0.9)
        self._structured_model = self._model.with_structured_output(WorldSchema)
        logger.info("Chat model created successfully")
        self._tracer = tracer
        logger.info("WorldGenerator.__init__ complete")

    async def _agenerate(self, prompt: str) -> str:
        """Async implementation of generation."""
        logger.info("_agenerate: calling model.ainvoke()...")
        config = {"callbacks": [self._tracer]} if self._tracer else {}
        response = await self._model.ainvoke(prompt, config=config)
        logger.info("_agenerate: model.ainvoke() returned successfully")
        return response.content

    async def _agenerate_structured(self, prompt: str) -> WorldSchema | None:
        """Generate world using structured output.

        Returns:
            WorldSchema if successful, None if structured output fails.
        """
        logger.info("_agenerate_structured: calling structured model...")
        config = {"callbacks": [self._tracer]} if self._tracer else {}
        try:
            response = await self._structured_model.ainvoke(prompt, config=config)
            logger.info("_agenerate_structured: structured output successful")
            return response
        except Exception as e:
            logger.warning(f"Structured output failed: {type(e).__name__}: {e}")
            return None

    def generate_world(
        self, player_id: str, player_name: str | None = None
    ) -> dict[str, Any]:
        """Generate a new world for a player using AI."""
        name = player_name or f"Bard {player_id[:8]}"

        prompt = WORLD_GENERATION_PROMPT.format(player_name=name)
        logger.info(f"generate_world: prompt length={len(prompt)}")

        try:
            # Try 1: Use structured output (most reliable)
            world_schema = asyncio.run(self._agenerate_structured(prompt))
            if world_schema is not None:
                logger.info("World generated via structured output")
                return self._validate_world_data(world_schema.model_dump())

            # Try 2: Fall back to regex parsing of raw response
            logger.info("Falling back to regex-based parsing")
            content = asyncio.run(self._agenerate(prompt))
            return self._parse_world_response(content)
        except Exception as e:
            logger.warning(f"World generation failed, using default world: {e}")
            return self._get_default_world()

    def _parse_world_response(self, content: str) -> dict[str, Any]:
        """Parse the AI response into structured world data."""
        content_preview = content[:500] + "..." if len(content) > 500 else content

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning(f"No JSON found in response: {content_preview}")
                return self._get_default_world()

        try:
            world_data = json.loads(json_str)
            return self._validate_world_data(world_data)
        except json.JSONDecodeError as e:
            json_preview = json_str[:200] + "..." if len(json_str) > 200 else json_str
            logger.warning(f"JSON decode failed: {e}. Content: {json_preview}")
            return self._get_default_world()

    def _validate_world_data(self, data: dict) -> dict[str, Any]:
        """Validate and normalize world data."""
        # Ensure required fields
        required_fields = [
            "name",
            "theme",
            "story_arc",
            "final_monster",
            "rescue_target",
            "locations",
        ]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return self._get_default_world()

        # Validate locations
        if not isinstance(data["locations"], list) or len(data["locations"]) < 3:
            loc_info = (
                f"type={type(data.get('locations')).__name__}, "
                f"len={len(data['locations']) if isinstance(data.get('locations'), list) else 'N/A'}"
            )
            logger.warning(f"Invalid locations (expected list with 3+ items): {loc_info}")
            return self._get_default_world()

        # Normalize locations
        exercise_types = [e.value for e in ExerciseType]
        for i, loc in enumerate(data["locations"]):
            # Ensure required location fields
            if "name" not in loc:
                loc["name"] = f"Village {i + 1}"
            if "description" not in loc:
                loc["description"] = "A mysterious place in the realm."
            if "type" not in loc:
                loc["type"] = LocationType.VILLAGE.value
            if "exercise_focus" not in loc or loc["exercise_focus"] not in exercise_types:
                loc["exercise_focus"] = exercise_types[i % len(exercise_types)]

        # Add a tavern if not present
        has_tavern = any(loc.get("type") == LocationType.TAVERN.value for loc in data["locations"])
        if not has_tavern:
            # Convert the second-to-last location to a tavern
            if len(data["locations"]) >= 2:
                data["locations"][-2]["type"] = LocationType.TAVERN.value

        # Add a dungeon for the final quest if not present
        has_dungeon = any(
            loc.get("type") == LocationType.DUNGEON.value for loc in data["locations"]
        )
        if not has_dungeon:
            data["locations"].append(
                {
                    "name": f"Lair of {data['final_monster']}",
                    "description": f"The dark domain where {data['final_monster']} holds {data['rescue_target']} captive.",
                    "type": LocationType.DUNGEON.value,
                    "exercise_focus": ExerciseType.HARMONY.value,
                }
            )

        return data

    def _get_default_world(self) -> dict[str, Any]:
        """Return a default world if generation fails."""
        return {
            "name": "The Melodic Realm",
            "theme": "A land where music holds magical power",
            "story_arc": "Long ago, the realm was filled with harmony. But the Discord Dragon has captured the Royal Composer, and only a brave bard can restore the music.",
            "final_monster": "The Discord Dragon",
            "rescue_target": "The Royal Composer",
            "locations": [
                {
                    "name": "Rhythmwood Village",
                    "description": "A peaceful village where the heartbeat of music begins. The villagers tap their feet to an eternal rhythm.",
                    "type": LocationType.VILLAGE.value,
                    "exercise_focus": ExerciseType.RHYTHM.value,
                },
                {
                    "name": "Melody Meadows",
                    "description": "Rolling hills where the wind carries ancient tunes. Flowers bloom in musical patterns.",
                    "type": LocationType.VILLAGE.value,
                    "exercise_focus": ExerciseType.MELODY.value,
                },
                {
                    "name": "The Harmonious Tavern",
                    "description": "A legendary inn where bards gather to share songs and stories. The perfect place to practice your craft.",
                    "type": LocationType.TAVERN.value,
                    "exercise_focus": ExerciseType.HARMONY.value,
                },
                {
                    "name": "Chord Crossing",
                    "description": "A mystical bridge where multiple musical paths converge. The echoes of countless melodies linger here.",
                    "type": LocationType.VILLAGE.value,
                    "exercise_focus": ExerciseType.EAR_TRAINING.value,
                },
                {
                    "name": "Lair of The Discord Dragon",
                    "description": "The dark cavern where The Discord Dragon holds The Royal Composer captive. Only the complete Hero's Ballad can charm the beast.",
                    "type": LocationType.DUNGEON.value,
                    "exercise_focus": ExerciseType.HARMONY.value,
                },
            ],
        }


