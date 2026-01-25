"""Player repository for data access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from resolute.db.models import Player


class PlayerRepository:
    """Pure data access for Player entities."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, player_id: str) -> Player | None:
        """Get a player by ID."""
        result = self.session.execute(select(Player).where(Player.id == player_id))
        return result.scalar_one_or_none()

    def create(self, player_id: str, name: str | None = None) -> Player:
        """Create a new player."""
        player = Player(id=player_id, name=name or f"Bard {player_id[:8]}")
        self.session.add(player)
        self.session.flush()
        return player

    def update(self, player: Player) -> Player:
        """Update a player."""
        self.session.add(player)
        self.session.flush()
        return player
