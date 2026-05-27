import functools

from src.config.default_config import TrackDefaults
from src.config.config_manager import resolve_config
from src.config.compiler import compile_session_config
from src.config.config import SessionMode
from src.core.engine import CarbonTrackerEngine


def track(config: TrackDefaults | None = None, **overrides):
    """
    Decorator to track the carbon footprint of a function.

    Accepts a TrackDefaults config or keyword overrides.
    See TrackDefaults for the full list of configurable fields.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if config is not None:
                effective = config.model_copy(update=overrides)
            else:
                effective = TrackDefaults(**overrides)

            resolved = resolve_config(effective)
            session_config = compile_session_config(
                resolved, mode=SessionMode.PYTHON_DECORATOR
            )
            engine = CarbonTrackerEngine(session_config)
            try:
                return func(*args, **kwargs)
            finally:
                engine.finish()
        return wrapper
    return decorator
