import subprocess
import sys
from src.config.default_config import TrackDefaults
from src.config.config_manager import resolve_config
from src.config.compiler import compile_session_config
from src.config.config import SessionMode
from src.core.engine import CarbonTrackerEngine


def cli_run(command: list[str], config: TrackDefaults | None = None):
    """
    Bare minimum CLI entry point.
    Wraps an arbitrary command with carbon tracking.

    Usage (future):
        carbontracker python train.py
    """
    effective = config or TrackDefaults()
    resolved = resolve_config(effective)
    session_config = compile_session_config(resolved, mode=SessionMode.SUBPROCESS)
    engine = CarbonTrackerEngine(session_config)

    try:
        result = subprocess.run(command)
        sys.exit(result.returncode)
    finally:
        engine.finish()


def cli_init():
    """
    Bare minimum init entry point.
    Future: interactive wizard that saves global/local configs.
    """
    raise NotImplementedError("CLI init wizard not yet implemented")


def cli_watch(log_dir: str):
    """
    Bare minimum watch entry point.
    Future: opens a TUI dashboard reading from log_dir.
    """
    raise NotImplementedError("CLI watch not yet implemented")


def main():
    """
    Minimal arg dispatch — future: replace with Click/Typer.
    """
    args = sys.argv[1:]
    if not args:
        print("Usage: carbontracker <init|watch|COMMAND>")
        sys.exit(1)

    if args[0] == "init":
        cli_init()
    elif args[0] == "watch":
        cli_watch(args[1] if len(args) > 1 else "./carbontracker_logs/")
    else:
        cli_run(args)
