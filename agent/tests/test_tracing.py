"""Tests for Opik tracing integration."""

import sys
from unittest.mock import MagicMock, patch


class TestTracing:
    """Tests for the tracing module."""

    def test_setup_tracing_no_api_key(self, monkeypatch):
        """Test that tracing is disabled without API key."""
        monkeypatch.setenv("OPIK_API_KEY", "")

        # Clear the settings cache
        from resolute.config import get_settings

        get_settings.cache_clear()

        from resolute.tracing import setup_tracing

        result = setup_tracing()
        assert result is False

    def test_setup_tracing_with_api_key(self, monkeypatch):
        """Test that tracing is enabled with API key."""
        monkeypatch.setenv("OPIK_API_KEY", "test-opik-key")

        # Clear the settings cache
        from resolute.config import get_settings

        get_settings.cache_clear()

        # Create mock opik module
        mock_opik = MagicMock()
        mock_opik_integrations = MagicMock()
        mock_opik_integrations.langchain = MagicMock()
        mock_opik_integrations.langchain.OpikTracer = MagicMock()

        # Patch the imports
        with patch.dict(
            sys.modules,
            {
                "opik": mock_opik,
                "opik.integrations": mock_opik_integrations,
                "opik.integrations.langchain": mock_opik_integrations.langchain,
            },
        ):
            # Need to reimport to get the patched module
            import importlib

            import resolute.tracing as tracing_module

            importlib.reload(tracing_module)

            result = tracing_module.setup_tracing()
            assert result is True
            mock_opik.configure.assert_called_once()

    def test_get_tracer_no_api_key(self, monkeypatch):
        """Test that get_tracer returns None without API key."""
        monkeypatch.setenv("OPIK_API_KEY", "")

        # Clear the settings cache
        from resolute.config import get_settings

        get_settings.cache_clear()

        from resolute.tracing import get_tracer

        tracer = get_tracer()
        assert tracer is None

    def test_get_tracer_with_api_key(self, monkeypatch):
        """Test that get_tracer returns tracer with API key."""
        monkeypatch.setenv("OPIK_API_KEY", "test-opik-key")

        # Clear the settings cache
        from resolute.config import get_settings

        get_settings.cache_clear()

        # Create mock opik module
        mock_tracer_instance = MagicMock()
        mock_tracer_class = MagicMock(return_value=mock_tracer_instance)
        mock_opik_integrations = MagicMock()
        mock_opik_integrations.langchain = MagicMock()
        mock_opik_integrations.langchain.OpikTracer = mock_tracer_class

        # Patch the imports
        with patch.dict(
            sys.modules,
            {
                "opik.integrations": mock_opik_integrations,
                "opik.integrations.langchain": mock_opik_integrations.langchain,
            },
        ):
            # Need to reimport to get the patched module
            import importlib

            import resolute.tracing as tracing_module

            importlib.reload(tracing_module)

            tracer = tracing_module.get_tracer()
            assert tracer is mock_tracer_instance
