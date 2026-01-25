"""Application context - central container for shared dependencies."""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from resolute.config import Settings
from resolute.game.exercise_timer import ExerciseTimer

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Container for application-wide dependencies.

    Initialize once at app startup via create_context().
    """

    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    exercise_timer: ExerciseTimer
    tracer: object | None = None

    # Lazy-initialized
    _world_generator: object | None = None

    @property
    def world_generator(self):
        """Get or create the world generator (lazy to avoid slow API init at startup)."""
        if self._world_generator is None:
            logger.info("Initializing world generator (lazy load)")
            from resolute.game.world_generator import WorldGenerator

            self._world_generator = WorldGenerator(
                model=self.settings.model,
                tracer=self.tracer,
            )
        return self._world_generator

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get a database session as a context manager."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def create_context(settings: Settings | None = None) -> AppContext:
    """Create and return a fully initialized application context."""
    logger.info("Creating application context")

    if settings is None:
        from resolute.config import get_settings

        settings = get_settings()

    # Create database engine
    sync_url = settings.database_url.replace("+aiosqlite", "")
    engine = create_engine(sync_url, echo=False, future=True)
    logger.debug(f"Database engine created: {sync_url}")

    # Create session factory
    session_factory = sessionmaker(engine, class_=Session, expire_on_commit=False)

    # Create exercise timer
    exercise_timer = ExerciseTimer()

    # Create tracer if configured
    tracer = _create_tracer(settings)

    logger.info("Application context created successfully")

    return AppContext(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        exercise_timer=exercise_timer,
        tracer=tracer,
    )


def _create_tracer(settings: Settings):
    """Create tracer if Opik is configured."""
    if not settings.has_opik_api_key:
        logger.debug("Opik API key not configured, tracing disabled")
        return None

    try:
        import opik
        from opik.integrations.langchain import OpikTracer

        opik.configure(
            api_key=settings.opik_api_key,
            workspace=settings.opik_workspace,
            force=True,
        )
        logger.info(f"Opik tracer configured for project: {settings.opik_project_name}")
        return OpikTracer(project_name=settings.opik_project_name)
    except ImportError:
        logger.warning("Opik package not installed, tracing disabled")
        return None
