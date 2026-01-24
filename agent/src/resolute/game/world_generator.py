"""AI-powered world generation for ResoLute."""

import json
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from resolute.agent.prompts import WORLD_GENERATION_PROMPT
from resolute.config import get_settings
from resolute.db.models import ExerciseType, LocationType


class WorldGenerator:
    """Generates unique fantasy worlds using AI."""

    def __init__(self, model: ChatGoogleGenerativeAI | None = None):
        if model is None:
            settings = get_settings()
            self._model = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.google_api_key,
                temperature=0.9,  # Higher creativity for world generation
            )
        else:
            self._model = model

    async def generate_world(
        self, player_id: str, player_name: str | None = None
    ) -> dict[str, Any]:
        """Generate a new world for a player using AI."""
        name = player_name or f"Bard {player_id[:8]}"

        prompt = WORLD_GENERATION_PROMPT.format(player_name=name)

        response = await self._model.ainvoke(prompt)

        # Parse the JSON response
        world_data = self._parse_world_response(response.content)

        return world_data

    def _parse_world_response(self, content: str) -> dict[str, Any]:
        """Parse the AI response into structured world data."""
        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Fall back to default world
                return self._get_default_world()

        try:
            world_data = json.loads(json_str)
            return self._validate_world_data(world_data)
        except json.JSONDecodeError:
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
                return self._get_default_world()

        # Validate locations
        if not isinstance(data["locations"], list) or len(data["locations"]) < 3:
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


# Singleton instance
_generator: WorldGenerator | None = None


def get_world_generator() -> WorldGenerator:
    """Get the global world generator instance."""
    global _generator
    if _generator is None:
        _generator = WorldGenerator()
    return _generator
