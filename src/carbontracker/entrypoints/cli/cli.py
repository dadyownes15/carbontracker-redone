import click
from pathlib import Path

from carbontracker.config.config_manager import resolve_overrides
from carbontracker.config.project_init import init_global_config, init_project_config
from carbontracker.core.event_codec import events_from_jsonl_lines
from carbontracker.core.events import DiagnosticEvent
from carbontracker.core.engine import CarbonTrackerEngine
from carbontracker.core.runtime import RuntimeOptions, build_subprocess_runtime
from carbontracker.providers.carbon_intensity.location import resolve_location


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
@click.option("--project-name", type=str, help="Name of the project")
@click.option("--run-name", type=str, help="Name of this run")
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

    options = RuntimeOptions.from_mapping(overrides)
    runtime = build_subprocess_runtime(command=list(command), options=options)
    engine = CarbonTrackerEngine(runtime)

    try:
        engine.wait_for_observer()
    finally:
        engine.finish()


@main.command()
@click.option("--global", "global_config", is_flag=True, help="Write user-level defaults")
@click.option("--project-name", type=str, help="Project name for local config")
@click.option("--log-dir", type=str, help="Default project log directory")
@click.option("--components", multiple=True, type=str, help="Default components to track")
@click.option("--power-sampling-interval", type=float, help="Default power sampling interval")
@click.option("--intensity-sampling-interval", type=float, help="Default intensity sampling interval")
@click.option("--intensity-method", type=str, help="Default intensity method")
@click.option("--static-carbon-intensity-g-per-kwh", type=float, help="Static intensity fallback")
@click.option("--api-key", multiple=True, type=(str, str), help="Global API key as PROVIDER VALUE")
@click.option("--location", type=str, help="Global default location")
@click.option("--pue", type=float, help="Global default PUE")
def init(global_config, **kwargs):
    """Initialize CarbonTracker config."""
    if global_config:
        raw_location = kwargs.get("location")
        location = (
            resolve_location(raw_location, auto_detect=False).location
            if raw_location
            else None
        )
        api_keys = dict(kwargs.get("api_key") or ())
        path = init_global_config(
            api_keys=api_keys,
            default_location=location,
            default_pue=kwargs.get("pue"),
        )
        click.echo(f"Wrote global config: {path}")
        return

    components = kwargs.get("components")
    path = init_project_config(
        project_name=kwargs.get("project_name"),
        log_dir=kwargs.get("log_dir"),
        components=components if components else None,
        power_sampling_interval=kwargs.get("power_sampling_interval"),
        intensity_sampling_interval=kwargs.get("intensity_sampling_interval"),
        intensity_method=kwargs.get("intensity_method"),
        static_carbon_intensity_g_per_kwh=kwargs.get(
            "static_carbon_intensity_g_per_kwh"
        ),
    )
    click.echo(f"Wrote project config: {path}")


@main.command(context_settings={"ignore_unknown_options": True})
@click.argument("command", nargs=-1, required=True)
@click.option("--project-name", type=str, help="Name of the project")
@click.option("--run-name", type=str, help="Name of this run")
@click.option("--log-dir", type=str, help="Directory to save logs")
@click.option("--pue", type=float, help="Power Usage Effectiveness")
@click.option("--components", multiple=True, type=str, help="Components to track (cpu, gpu, ram)")
@click.option("--power-sampling-interval", type=float, help="Interval for power sampling in seconds")
@click.option("--intensity-sampling-interval", type=float, help="Interval for intensity sampling in seconds")
def watch(command, **kwargs):
    """Runs a command with live TUI-oriented subprocess output events."""
    user_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    if "components" in user_kwargs and not user_kwargs["components"]:
        del user_kwargs["components"]
    overrides = resolve_overrides(**user_kwargs)
    _reject_unsupported_options(overrides)
    options = RuntimeOptions.from_mapping(overrides)
    runtime = build_subprocess_runtime(
        command=list(command),
        options=options,
        capture_output_events=True,
    )
    engine = CarbonTrackerEngine(runtime)

    try:
        engine.wait_for_observer()
    finally:
        engine.finish()


@main.command()
@click.argument("path", required=False)
def replay(path):
    """Reads JSONL event logs and reports decode diagnostics."""
    if path is None:
        overrides = resolve_overrides()
        options = RuntimeOptions.from_mapping(overrides)
        log_path = Path(options.log_dir)
    else:
        log_path = Path(path)
    if log_path.is_dir():
        files = sorted(log_path.glob("*_events.jsonl"))
    else:
        files = [log_path]

    if not files:
        click.echo(f"No JSONL logs found at {log_path}")
        return

    for file_path in files:
        with open(file_path) as handle:
            for event in events_from_jsonl_lines(handle):
                if isinstance(event, DiagnosticEvent):
                    click.echo(f"[{event.severity.value}] {event.message}", err=True)
                else:
                    click.echo(f"[Replay] {type(event).__name__}")


if __name__ == "__main__":
    main()
