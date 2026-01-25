"""World repository for data access."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from resolute.db.models import Location, LocationType, Song, SongSegment, World


class WorldRepository:
    """Pure data access for World and Location entities."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_player_id(self, player_id: str) -> World | None:
        """Get a world by player ID with all locations loaded."""
        result = self.session.execute(
            select(World)
            .where(World.player_id == player_id)
            .options(selectinload(World.locations).selectinload(Location.segments))
        )
        return result.scalar_one_or_none()

    def create(
        self,
        player_id: str,
        name: str,
        theme: str,
        story_arc: str,
        final_monster: str,
        rescue_target: str,
    ) -> World:
        """Create a new world."""
        world = World(
            player_id=player_id,
            name=name,
            theme=theme,
            story_arc=story_arc,
            final_monster=final_monster,
            rescue_target=rescue_target,
        )
        self.session.add(world)
        self.session.flush()
        return world

    def get_location_by_id(self, location_id: int) -> Location | None:
        """Get a location by ID."""
        result = self.session.execute(select(Location).where(Location.id == location_id))
        return result.scalar_one_or_none()

    def get_location_with_segments(self, location_id: int) -> Location | None:
        """Get a location with segments eagerly loaded."""
        result = self.session.execute(
            select(Location)
            .where(Location.id == location_id)
            .options(selectinload(Location.segments))
        )
        return result.scalar_one_or_none()

    def get_locations_for_world(self, world_id: int) -> list[Location]:
        """Get all locations for a world ordered by index."""
        result = self.session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .order_by(Location.order_index)
        )
        return list(result.scalars().all())

    def get_unlocked_destinations(
        self, world_id: int, exclude_location_id: int
    ) -> list[Location]:
        """Get unlocked locations for travel destinations."""
        result = self.session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .where(Location.is_unlocked.is_(True))
            .where(Location.id != exclude_location_id)
            .order_by(Location.order_index)
        )
        return list(result.scalars().all())

    def get_next_locked_location(self, world_id: int) -> Location | None:
        """Get the next locked location in sequence."""
        result = self.session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .where(Location.is_unlocked.is_(False))
            .order_by(Location.order_index)
            .limit(1)
        )
        return result.scalar_one_or_none()

    def get_first_location(self, world_id: int) -> Location | None:
        """Get the first location in a world."""
        result = self.session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .order_by(Location.order_index)
            .limit(1)
        )
        return result.scalar_one_or_none()

    def get_non_dungeon_locations(self, world_id: int) -> list[Location]:
        """Get locations excluding dungeons (for segment distribution)."""
        result = self.session.execute(
            select(Location)
            .where(Location.world_id == world_id)
            .where(Location.location_type != LocationType.DUNGEON.value)
            .order_by(Location.order_index)
        )
        return list(result.scalars().all())

    def create_location(
        self,
        world_id: int,
        name: str,
        description: str,
        location_type: str,
        exercise_focus: str | None,
        order_index: int,
        is_unlocked: bool = False,
    ) -> Location:
        """Create a new location."""
        location = Location(
            world_id=world_id,
            name=name,
            description=description,
            location_type=location_type,
            exercise_focus=exercise_focus,
            order_index=order_index,
            is_unlocked=is_unlocked,
        )
        self.session.add(location)
        self.session.flush()
        return location

    def unlock_location(self, location: Location) -> Location:
        """Unlock a location."""
        location.is_unlocked = True
        self.session.flush()
        return location

    def get_default_song(self) -> Song | None:
        """Get the default final song."""
        result = self.session.execute(
            select(Song).where(Song.is_final_song.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()

    def get_song_segments(self, song_id: int) -> list[SongSegment]:
        """Get all segments for a song ordered by index."""
        result = self.session.execute(
            select(SongSegment)
            .where(SongSegment.song_id == song_id)
            .order_by(SongSegment.segment_index)
        )
        return list(result.scalars().all())

    def get_segment_by_id(self, segment_id: int) -> SongSegment | None:
        """Get a song segment by ID."""
        result = self.session.execute(
            select(SongSegment).where(SongSegment.id == segment_id)
        )
        return result.scalar_one_or_none()

    def update_segment_location(self, segment: SongSegment, location_id: int) -> None:
        """Update a segment's location."""
        segment.location_id = location_id
        self.session.flush()
