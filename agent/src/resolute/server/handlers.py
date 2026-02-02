"""Message handlers for game logic - testable without WebSocket mocking."""

import logging

from resolute.agent import MentorAgent
from resolute.context import AppContext
from resolute.game.services import ExerciseService, PlayerService, QuestService, WorldService
from resolute.server.messages import (
    ServerMessage,
    auth_failed_message,
    auth_success_message,
    error_message,
    exercise_complete_message,
    exercise_state_message,
    game_complete_message,
    inventory_update_message,
    location_state_message,
    performance_result_message,
    player_state_message,
    segment_collected_message,
    world_state_message,
)

logger = logging.getLogger(__name__)

# Hardcoded credentials for initial implementation
# TODO: Replace with proper user database
VALID_CREDENTIALS = {
    "hero": "quest123",
    "bard": "music456",
    "test": "test",
    "demo": "demo",
}


class AuthHandler:
    """Handles authentication before game session starts."""

    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def authenticate(self, username: str, password: str) -> tuple[bool, ServerMessage, str | None]:
        """Authenticate a user and return success status, message, and player_id.

        Returns:
            Tuple of (success, message, player_id or None)
        """
        if not username or not password:
            return False, auth_failed_message("Username and password are required"), None

        # Check credentials
        expected_password = VALID_CREDENTIALS.get(username.lower())
        if expected_password is None or password != expected_password:
            logger.warning(f"Failed login attempt for user: {username}")
            return False, auth_failed_message("Invalid username or password"), None

        # Generate player_id from username
        player_id = f"player_{username.lower()}"

        # Get or create player in database
        with self.ctx.session() as session:
            player_service = PlayerService(session)
            player_result = player_service.get_or_create(player_id, name=username)

            if player_result.is_err:
                return False, auth_failed_message(f"Failed to create player: {player_result.error}"), None

            player = player_result.unwrap()
            player_data = {
                "id": player.id,
                "name": player.name,
                "level": player.level,
                "xp": player.xp,
                "gold": player.gold,
                "reputation": player.reputation,
            }

        logger.info(f"User authenticated: {username} -> {player_id}")
        return True, auth_success_message(player_id, player_data), player_id


class MessageHandler:
    """Handles game messages - testable without WebSocket mocking."""

    def __init__(
        self,
        player_id: str,
        ctx: AppContext,
        agent: MentorAgent | None = None,
    ):
        self.player_id = player_id
        self.ctx = ctx
        self.agent = agent

    def handle_world(self) -> ServerMessage:
        """Handle world state request, generating if needed."""
        logger.info(f"[{self.player_id}] World request")
        with self.ctx.session() as session:
            world_service = WorldService(session)
            player_service = PlayerService(session)

            result = world_service.get_or_generate(self.player_id)
            if result.is_err:
                return error_message(result.error)

            world_data = result.unwrap()

            if world_data.get("needs_generation"):
                # Generate a new world (sync AI call)
                logger.info(f"[{self.player_id}] Generating new world...")
                generator = self.ctx.world_generator

                player_result = player_service.get_player(self.player_id)
                player_name = (
                    player_result.unwrap().name
                    if player_result.is_ok
                    else f"Bard {self.player_id[:8]}"
                )

                try:
                    generated_data = generator.generate_world(self.player_id, player_name)
                    logger.info(
                        f"[{self.player_id}] World generated: {generated_data.get('name', 'unknown')}"
                    )

                    # Create the world in the database
                    create_result = world_service.create_world(
                        player_id=self.player_id,
                        name=generated_data["name"],
                        theme=generated_data["theme"],
                        story_arc=generated_data["story_arc"],
                        final_monster=generated_data["final_monster"],
                        rescue_target=generated_data["rescue_target"],
                        locations=generated_data["locations"],
                    )

                    if create_result.is_err:
                        return error_message(create_result.error)

                    world = create_result.unwrap()
                    return world_state_message(world.to_dict())
                except Exception as e:
                    logger.error(f"World generation failed: {e}")
                    return error_message(f"Failed to generate world: {str(e)}")
            else:
                return world_state_message(world_data["world"])

    def handle_location(self) -> ServerMessage:
        """Handle location state request - returns current location details."""
        logger.info(f"[{self.player_id}] Location request")
        with self.ctx.session() as session:
            player_service = PlayerService(session)
            quest_service = QuestService(session)

            # Get current location
            loc_result = player_service.get_current_location(self.player_id)
            if loc_result.is_err:
                return error_message(loc_result.error)

            location_info = loc_result.unwrap()

            # Get inventory for song fragments
            inv_result = quest_service.get_inventory(self.player_id)
            inventory = inv_result.unwrap() if inv_result.is_ok else {}

            # Combine location and inventory data
            location_data = {
                "location": location_info.get("location", {}),
                "available_destinations": location_info.get("available_destinations", []),
                "available_segments": location_info.get("available_segments", []),
                "collected_segments": inventory.get("collected_segments", []),
                "total_segments": inventory.get("total_segments", 4),
            }

            return location_state_message(location_data)

    def handle_player(self) -> ServerMessage:
        """Handle player stats request."""
        logger.info(f"[{self.player_id}] Player stats request")
        with self.ctx.session() as session:
            player_service = PlayerService(session)

            result = player_service.get_player(self.player_id)
            if result.is_err:
                return error_message(result.error)

            player = result.unwrap()
            player_data = {
                "id": player.id,
                "name": player.name,
                "level": player.level,
                "xp": player.xp,
                "xp_to_next_level": 100 * player.level,  # Simple formula
                "gold": player.gold,
                "reputation": player.reputation,
            }

            return player_state_message(player_data)

    def handle_travel(self, destination: str) -> ServerMessage:
        """Handle travel request to start an exercise."""
        with self.ctx.session() as session:
            player_service = PlayerService(session)
            exercise_service = ExerciseService(session, self.ctx.exercise_timer)

            # Get available destinations
            loc_result = player_service.get_current_location(self.player_id)
            if loc_result.is_err:
                return error_message(loc_result.error)

            location_info = loc_result.unwrap()
            destinations = location_info.get("available_destinations", [])

            dest_match = None
            for d in destinations:
                if destination.lower() in d["name"].lower():
                    dest_match = d
                    break

            if dest_match is None:
                available = [d["name"] for d in destinations]
                return error_message(f"Unknown destination. Available: {', '.join(available)}")

            result = exercise_service.start_travel(self.player_id, dest_match["id"])
            if result.is_err:
                return error_message(result.error)

            return exercise_state_message(result.unwrap()["session"])

    def handle_exercise(self, action: str) -> ServerMessage:
        """Handle exercise actions (check/complete)."""
        with self.ctx.session() as session:
            exercise_service = ExerciseService(session, self.ctx.exercise_timer)

            if action == "check":
                result = exercise_service.check_exercise(self.player_id)
                if result.is_err:
                    return error_message(result.error)
                return exercise_state_message(result.unwrap())

            elif action == "complete":
                result = exercise_service.complete_exercise(self.player_id)
                if result.is_err:
                    return error_message(result.error)
                return exercise_complete_message(result.unwrap())

            else:
                return error_message(f"Unknown exercise action: {action}")

    def handle_collect(self, segment_id: int) -> ServerMessage:
        """Handle segment collection."""
        with self.ctx.session() as session:
            quest_service = QuestService(session)
            result = quest_service.collect_segment(self.player_id, segment_id)

            if result.is_err:
                return error_message(result.error)

            return segment_collected_message(result.unwrap())

    def handle_perform(self) -> ServerMessage:
        """Handle tavern performance."""
        with self.ctx.session() as session:
            quest_service = QuestService(session)
            result = quest_service.perform_at_tavern(self.player_id)

            if result.is_err:
                return error_message(result.error)

            return performance_result_message(result.unwrap())

    def handle_final_quest(self, action: str) -> ServerMessage:
        """Handle final quest actions."""
        with self.ctx.session() as session:
            quest_service = QuestService(session)

            if action == "check":
                result = quest_service.check_final_quest_ready(self.player_id)
                if result.is_err:
                    return error_message(result.error)

                data = result.unwrap()
                content = (
                    "You are ready for the final quest!"
                    if data["ready"]
                    else f"Collect more segments: {data['segments_collected']}/{data['segments_required']}"
                )
                return ServerMessage(
                    type="response",
                    content=content,
                    data=data,
                )

            elif action == "attempt":
                result = quest_service.complete_final_quest(self.player_id)
                if result.is_err:
                    return error_message(result.error)
                return game_complete_message(result.unwrap())

            else:
                return error_message(f"Unknown final quest action: {action}")

    def handle_inventory(self) -> ServerMessage:
        """Handle inventory request."""
        with self.ctx.session() as session:
            quest_service = QuestService(session)
            result = quest_service.get_inventory(self.player_id)

            if result.is_err:
                return error_message(result.error)

            return inventory_update_message(result.unwrap())

    def _get_game_state_context(self) -> str:
        """Fetch current game state and format as context for the agent."""
        with self.ctx.session() as session:
            player_service = PlayerService(session)
            quest_service = QuestService(session)

            lines = ["## Current Game State"]

            # Get current location
            loc_result = player_service.get_current_location(self.player_id)
            if loc_result.is_ok:
                location_info = loc_result.unwrap()
                loc = location_info.get("location", {})
                lines.append(f"Current Location: {loc.get('name', 'Unknown')} ({loc.get('location_type', 'unknown')})")

                # Uncollected segments at this location
                uncollected = location_info.get("uncollected_segments", [])
                if uncollected:
                    segment_names = [s.get("name", f"ID:{s.get('id')}") for s in uncollected]
                    lines.append(f"Available to collect here: {', '.join(segment_names)}")
                else:
                    lines.append("No segments available to collect at this location.")

                # Available destinations
                destinations = location_info.get("available_destinations", [])
                if destinations:
                    dest_names = [d.get("name", "Unknown") for d in destinations]
                    lines.append(f"Can travel to: {', '.join(dest_names)}")

            # Get inventory
            inv_result = quest_service.get_inventory(self.player_id)
            if inv_result.is_ok:
                inventory = inv_result.unwrap()
                collected = inventory.get("collected_segments", [])
                total = inventory.get("total_segments", 4)
                lines.append(f"Segments collected: {len(collected)}/{total}")
                if collected:
                    collected_names = [s.get("name", "Unknown") for s in collected]
                    lines.append(f"Collected: {', '.join(collected_names)}")

            return "\n".join(lines)

    def handle_chat(self, message: str) -> ServerMessage:
        """Handle chat message with game context."""
        logger.info(f"[{self.player_id}] Chat request: {message[:50]}...")
        if not self.agent:
            logger.error(f"[{self.player_id}] Agent not found")
            return error_message("Agent not found for this session")

        # Fetch current game state and include in context
        state_context = self._get_game_state_context()
        enriched_message = f"{state_context}\n\n## Player Message\n{message}"

        # Sync chat - run in thread pool from WebSocket handler
        logger.info(f"[{self.player_id}] Invoking agent...")
        response_content = self.agent.chat(enriched_message, thread_id=self.player_id)
        logger.info(f"[{self.player_id}] Agent response received: {response_content[:50]}...")

        return ServerMessage(
            type="response",
            content=response_content,
            metadata={"message_type": "chat"},
        )
