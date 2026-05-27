import subprocess
import sys
import time
import click

from src.config.config import SessionMode, SessionConfig
from src.config.config_manager import resolve_overrides
from src.core.engine import CarbonTrackerEngine


def _generate_default_name() -> str:
    return f"run_{int(time.time())}"


class PassThroughGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args:
            return super().parse_args(ctx, args)
        if args[0] in self.commands:
            return super().parse_args(ctx, args)
            
        # Route to the hidden 'run' command
        args.insert(0, 'run')
        return super().parse_args(ctx, args)


@click.group(cls=PassThroughGroup)
def main():
    """CarbonTracker: Track the carbon footprint of your code."""
    pass


@main.command(hidden=True)
@click.argument("command", nargs=-1, required=True)
@click.option("--project-name", type=str, help="Name of the run")
@click.option("--log-dir", type=str, help="Directory to save logs")
@click.option("--pue", type=float, help="Power Usage Effectiveness")
@click.option("--components", multiple=True, type=str, help="Components to track (cpu, gpu, ram)")
@click.option("--power-sampling-interval", type=float, help="Interval for power sampling in seconds")
@click.option("--intensity-sampling-interval", type=float, help="Interval for intensity sampling in seconds")
def run(command, **kwargs):
    """
    Wraps an arbitrary command with carbon tracking.
    """
    user_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    
    if "components" in user_kwargs and user_kwargs["components"]:
        from src.core.types import Component
        user_kwargs["components"] = [Component(c.lower()) for c in user_kwargs["components"]]
    elif "components" in user_kwargs:
        del user_kwargs["components"]

    overrides = resolve_overrides(**user_kwargs)
    
    if "project_name" in overrides:
        overrides["run_name"] = overrides.pop("project_name")
    else:
        overrides["run_name"] = _generate_default_name()

    config = SessionConfig(
        mode=SessionMode.SUBPROCESS,
        command=list(command),
        **overrides
    )
    engine = CarbonTrackerEngine(config)

    # Note: We no longer run subprocess here because SubprocessObserverThread does it!
    # The engine handles starting the observer which spawns the process.
    # We just need to wait for the engine/observer to finish.
    try:
        # Wait for the observer thread to finish executing the subprocess
        if hasattr(engine, 'observer_thread'):
            engine.observer_thread.join()
    finally:
        engine.finish()


@main.command()
def init():
    """Interactive wizard that saves global/local configs."""
    click.echo("CLI init wizard not yet implemented")


@main.command()
@click.argument("log_dir", default="./carbontracker_logs/", required=False)
def watch(log_dir):
    """Opens a TUI dashboard reading from log_dir."""
    click.echo(f"CLI watch not yet implemented. Log dir: {log_dir}")


if __name__ == "__main__":
    main()
