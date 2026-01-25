"""Message handlers for game logic - testable without WebSocket mocking."""

import logging

from resolute.agent import MentorAgent
from resolute.context import AppContext
from resolute.game.services import ExerciseService, PlayerService, QuestService, WorldService
from resolute.server.messages import (
    ServerMessage,
    error_message,
    exercise_complete_message,
    exercise_state_message,
    game_complete_message,
    inventory_update_message,
    performance_result_message,
    segment_collected_message,
    world_state_message,
)

logger = logging.getLogger(__name__)


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

    def handle_chat(self, message: str) -> ServerMessage:
        """Handle chat message with game context."""
        logger.info(f"[{self.player_id}] Chat request: {message[:50]}...")
        if not self.agent:
            logger.error(f"[{self.player_id}] Agent not found")
            return error_message("Agent not found for this session")

        # Sync chat - run in thread pool from WebSocket handler
        logger.info(f"[{self.player_id}] Invoking agent...")
        response_content = self.agent.chat(message, thread_id=self.player_id)
        logger.info(f"[{self.player_id}] Agent response received: {response_content[:50]}...")

        return ServerMessage(
            type="response",
            content=response_content,
            metadata={"message_type": "chat"},
        )
