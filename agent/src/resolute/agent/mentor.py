"""MentorAgent - LangGraph ReAct agent for guiding players."""

import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session, sessionmaker

from resolute.agent.prompts import MENTOR_SYSTEM_PROMPT
from resolute.agent.tools import create_tools_for_player
from resolute.game.exercise_timer import ExerciseTimer

logger = logging.getLogger(__name__)


class MentorAgent:
    """AI mentor agent that guides players through their musical journey."""

    def __init__(
        self,
        player_id: str,
        session_factory: sessionmaker[Session],
        timer: ExerciseTimer,
        model: str,
        tracer: object | None = None,
        player_name: str = "Adventurer",
    ):
        """Initialize the MentorAgent.

        Args:
            player_id: The unique identifier for the player.
            session_factory: Factory for creating database sessions.
            timer: The exercise timer instance.
            model: LLM model identifier (e.g., "google_genai/gemini-2.0-flash").
            tracer: Optional tracer for observability.
            player_name: The display name of the player being mentored.
        """
        self.player_id = player_id
        self.player_name = player_name

        # Initialize LLM
        from resolute.llm import create_chat_model

        self.llm = create_chat_model(model, temperature=0.7)

        # Create memory for conversation persistence
        self.memory = MemorySaver()

        # Create system prompt
        self.system_prompt = MENTOR_SYSTEM_PROMPT.format(player_name=player_name)

        # Create tools
        self.tools = create_tools_for_player(player_id, session_factory, timer)

        # Create the ReAct agent
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.memory,
        )

        # Store tracer
        self.tracer = tracer

        logger.info(f"MentorAgent initialized for player: {player_name} (ID: {player_id})")

    def _get_config(self, thread_id: str) -> dict:
        """Get the configuration for agent invocation.

        Args:
            thread_id: The conversation thread ID.

        Returns:
            Configuration dictionary.
        """
        config = {"configurable": {"thread_id": thread_id}}

        if self.tracer:
            config["callbacks"] = [self.tracer]

        return config

    async def _achat(self, message: str, thread_id: str) -> str:
        """Async implementation of chat."""
        config = self._get_config(thread_id)

        # Build messages with system prompt
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=message),
        ]

        # Invoke the agent (async)
        logger.info(f"[{self.player_id}] Calling agent.ainvoke()...")
        result = await self.agent.ainvoke(
            {"messages": messages},
            config=config,
        )
        logger.info(f"[{self.player_id}] agent.ainvoke() returned")

        # Extract the response
        if result and "messages" in result:
            response_messages = result["messages"]
            if response_messages:
                return response_messages[-1].content

        return "I seem to have lost my train of thought. Could you repeat that?"

    def chat(self, message: str, thread_id: str | None = None) -> str:
        """Send a message to the agent and get a response.

        This is a sync wrapper that runs the async agent in a new event loop.
        Safe to call from a thread pool (e.g., asyncio.to_thread).

        Args:
            message: The user's message.
            thread_id: Optional thread ID for conversation persistence.

        Returns:
            The agent's response.
        """
        if thread_id is None:
            thread_id = self.player_id

        logger.info(f"[{self.player_id}] chat() called with message: {message[:50]}...")

        try:
            # Run async agent in a new event loop (safe from thread pool)
            return asyncio.run(self._achat(message, thread_id))

        except Exception as e:
            logger.error(f"[{self.player_id}] Error in agent chat: {e}")
            return f"Apologies, adventurer. I encountered a mystical interference: {str(e)}"
