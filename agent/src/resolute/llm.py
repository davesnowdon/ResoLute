"""LLM initialization - provider-agnostic model creation."""

import logging

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

# Load .env file into environment so LangChain can read API keys
load_dotenv()

logger = logging.getLogger(__name__)


def create_chat_model(model: str, temperature: float = 0.7) -> BaseChatModel:
    """Create a chat model from a provider/model_name string.

    Args:
        model: Model identifier in format "provider/model_name"
               (e.g., "google_genai/gemini-2.0-flash", "openai/gpt-4o")
        temperature: Model temperature (0.0-1.0)

    Returns:
        Configured chat model instance.

    Note:
        API keys are read from environment variables automatically:
        - GOOGLE_API_KEY for google_genai provider
        - OPENAI_API_KEY for openai provider
        - ANTHROPIC_API_KEY for anthropic provider
    """
    logger.debug(f"Creating chat model: {model} (temperature={temperature})")

    # Parse provider/model format
    if "/" in model:
        provider, model_name = model.split("/", 1)
    else:
        logger.error(f"Invalid model format: {model}")
        raise ValueError(
            f"Model must be in 'provider/model_name' format, got: {model}"
        )

    logger.info(f"Initializing LLM: provider={provider}, model={model_name}")
    return init_chat_model(model_name, model_provider=provider, temperature=temperature)
