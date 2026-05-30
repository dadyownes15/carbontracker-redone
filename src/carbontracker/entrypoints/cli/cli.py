import time
import click

from carbontracker.config.config_manager import resolve_overrides
from carbontracker.core.engine import CarbonTrackerEngine
from carbontracker.core.runtime import RuntimeOptions, build_subprocess_runtime


def _generate_default_name() -> str:
    return f"run_{int(time.time())}"


def _reject_unsupported_options(overrides: dict) -> None:
    unsupported: list[str] = []
    for key in (
        "predict_after",
        "predict_after_n_units",
        "predict_after_n_secounds",
        "predict_interval",
        "predict_interval_s",
        "total_duration",
        "total_units",
        "unit_name",
        "max_energy_kwh",
        "max_emissions_g",
        "on_breach_callback",
    ):
        if overrides.get(key) is not None:
            unsupported.append(key)

    if overrides.get("use_predicted_values"):
        unsupported.append("use_predicted_values")

    action_on_breach = overrides.get("action_on_breach")
    if action_on_breach not in (None, "log"):
        unsupported.append("action_on_breach")

    if unsupported:
        joined = ", ".join(unsupported)
        raise click.ClickException(
            f"Prediction and budget options are not supported yet: {joined}"
        )


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

    if "components" in user_kwargs and not user_kwargs["components"]:
        del user_kwargs["components"]

    overrides = resolve_overrides(**user_kwargs)
    _reject_unsupported_options(overrides)

    if "project_name" in overrides:
        overrides["run_name"] = overrides.pop("project_name")
    elif "run_name" not in overrides:
        overrides["run_name"] = _generate_default_name()

    options = RuntimeOptions.from_mapping(overrides)
    runtime = build_subprocess_runtime(command=list(command), options=options)
    engine = CarbonTrackerEngine(runtime)

    try:
        engine.wait_for_observer()
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
