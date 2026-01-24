"""Tracing module - Opik observability integration for LangChain."""

import logging

from resolute.config import get_settings

logger = logging.getLogger(__name__)

__all__ = ["setup_tracing", "get_tracer"]


def setup_tracing() -> bool:
    """
    Configure Opik tracing for LangChain.

    Returns:
        True if tracing was successfully configured, False otherwise.
    """
    settings = get_settings()

    if not settings.has_opik_api_key:
        logger.info("Opik API key not configured, tracing disabled")
        return False

    try:
        import opik

        opik.configure(
            api_key=settings.opik_api_key,
            workspace=settings.opik_workspace,
            force=True,  # Override cached config
        )

        # Enable LangChain integration
        from opik.integrations.langchain import OpikTracer

        # Create a global tracer instance
        _tracer = OpikTracer(project_name=settings.opik_project_name)

        logger.info(f"Opik tracing enabled for project: {settings.opik_project_name}")
        return True

    except ImportError as e:
        logger.warning(f"Opik not installed: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to configure Opik: {e}")
        return False


def get_tracer():
    """Get the Opik tracer for LangChain callbacks."""
    settings = get_settings()

    if not settings.has_opik_api_key:
        return None

    try:
        from opik.integrations.langchain import OpikTracer

        return OpikTracer(project_name=settings.opik_project_name)
    except ImportError:
        return None
