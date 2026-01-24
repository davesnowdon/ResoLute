"""MentorAgent - LangGraph ReAct agent for guiding players."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from resolute.agent.prompts import MENTOR_SYSTEM_PROMPT
from resolute.agent.tools import get_mentor_tools
from resolute.config import get_settings
from resolute.tracing import get_tracer

logger = logging.getLogger(__name__)


class MentorAgent:
    """AI mentor agent that guides players through their musical journey."""

    def __init__(self, player_name: str = "Adventurer"):
        """Initialize the MentorAgent.

        Args:
            player_name: The name of the player being mentored.
        """
        self.player_name = player_name
        self.settings = get_settings()

        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model=self.settings.gemini_model,
            google_api_key=self.settings.google_api_key,
            temperature=0.7,
        )

        # Get tools
        self.tools = get_mentor_tools()

        # Create memory for conversation persistence
        self.memory = MemorySaver()

        # Create system prompt
        self.system_prompt = MENTOR_SYSTEM_PROMPT.format(player_name=player_name)

        # Create the ReAct agent
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.memory,
        )

        # Get tracer if available
        self.tracer = get_tracer()

        logger.info(f"MentorAgent initialized for player: {player_name}")

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

    async def achat(self, message: str, thread_id: str | None = None) -> str:
        """Send a message to the agent and get a response.

        Args:
            message: The user's message.
            thread_id: Optional thread ID for conversation persistence.

        Returns:
            The agent's response.
        """
        if thread_id is None:
            thread_id = self.player_name

        config = self._get_config(thread_id)

        # Build messages with system prompt
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=message),
        ]

        try:
            # Invoke the agent
            result = await self.agent.ainvoke(
                {"messages": messages},
                config=config,
            )

            # Extract the response
            if result and "messages" in result:
                response_messages = result["messages"]
                if response_messages:
                    return response_messages[-1].content

            return "I seem to have lost my train of thought. Could you repeat that?"

        except Exception as e:
            logger.error(f"Error in agent chat: {e}")
            return f"Apologies, adventurer. I encountered a mystical interference: {str(e)}"

    def chat(self, message: str, thread_id: str | None = None) -> str:
        """Synchronous version of chat.

        Args:
            message: The user's message.
            thread_id: Optional thread ID for conversation persistence.

        Returns:
            The agent's response.
        """
        import asyncio

        return asyncio.run(self.achat(message, thread_id))
