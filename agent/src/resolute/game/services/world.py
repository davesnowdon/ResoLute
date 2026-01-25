"""World service for business logic."""

from sqlalchemy.orm import Session

from resolute.core.result import Result
from resolute.db.models import LocationType, World
from resolute.db.repositories import PlayerRepository, WorldRepository


class WorldService:
    """Business logic for world operations."""

    def __init__(self, session: Session):
        self.session = session
        self.player_repo = PlayerRepository(session)
        self.world_repo = WorldRepository(session)

    def get_or_generate(self, player_id: str) -> Result[dict]:
        """Get player's world or indicate generation is needed."""
        world = self.world_repo.get_by_player_id(player_id)
        if world is None:
            return Result.ok({"needs_generation": True, "player_id": player_id})
        return Result.ok({"needs_generation": False, "world": world.to_dict()})

    def get_world(self, player_id: str) -> Result[World]:
        """Get a player's world."""
        world = self.world_repo.get_by_player_id(player_id)
        if world is None:
            return Result.err("World not found")
        return Result.ok(world)

    def create_world(
        self,
        player_id: str,
        name: str,
        theme: str,
        story_arc: str,
        final_monster: str,
        rescue_target: str,
        locations: list[dict],
    ) -> Result[World]:
        """Create a new world for a player with locations."""
        # Ensure player exists
        player = self.player_repo.get_by_id(player_id)
        if player is None:
            player = self.player_repo.create(player_id)

        # Create world
        world = self.world_repo.create(
            player_id=player_id,
            name=name,
            theme=theme,
            story_arc=story_arc,
            final_monster=final_monster,
            rescue_target=rescue_target,
        )

        # Create locations
        for i, loc_data in enumerate(locations):
            self.world_repo.create_location(
                world_id=world.id,
                name=loc_data["name"],
                description=loc_data.get("description", ""),
                location_type=loc_data.get("type", LocationType.VILLAGE.value),
                exercise_focus=loc_data.get("exercise_focus"),
                order_index=i,
                is_unlocked=i == 0,  # First location is unlocked
            )

        # Distribute song segments across locations
        self._distribute_song_segments(world.id)

        # Set player's starting location
        first_location = self.world_repo.get_first_location(world.id)
        if first_location:
            player.current_location_id = first_location.id
            self.player_repo.update(player)

        # Reload world with all relationships
        world = self.world_repo.get_by_player_id(player_id)
        return Result.ok(world)

    def _distribute_song_segments(self, world_id: int) -> None:
        """Distribute song segments across world locations."""
        song = self.world_repo.get_default_song()
        if song is None:
            return

        # Get locations excluding dungeons
        locations = self.world_repo.get_non_dungeon_locations(world_id)

        # Get song segments
        segments = self.world_repo.get_song_segments(song.id)

        # Assign segments to locations
        for i, segment in enumerate(segments):
            if i < len(locations):
                self.world_repo.update_segment_location(segment, locations[i].id)

    def unlock_next_location(self, player_id: str) -> Result[bool]:
        """Unlock the next location in sequence."""
        world = self.world_repo.get_by_player_id(player_id)
        if world is None:
            return Result.err("World not found")

        for location in sorted(world.locations, key=lambda x: x.order_index):
            if not location.is_unlocked:
                self.world_repo.unlock_location(location)
                return Result.ok(True)

        return Result.ok(False)  # All locations already unlocked
