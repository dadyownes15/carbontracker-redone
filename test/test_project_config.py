import os
import stat

from click.testing import CliRunner

from carbontracker.config.config_manager import (
    get_global_config_file,
    get_local_config_file,
    load_local_config,
    resolve_overrides,
)
from carbontracker.config.project_init import init_global_config, init_project_config
from carbontracker.entrypoints.cli import cli as cli_module


def test_init_project_config_writes_local_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    path = init_project_config(project_name="demo", log_dir="logs")

    assert path == tmp_path / ".carbontracker" / "config.toml"
    assert path.exists()
    config = load_local_config()
    assert config["project_name"] == "demo"
    assert config["log_dir"] == "logs"
    assert config["components"] == ["cpu", "gpu", "ram"]


def test_init_global_config_writes_user_config_with_restricted_permissions(
    monkeypatch, tmp_path
):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    path = init_global_config(api_keys={"electricity_maps": "secret"}, default_pue=1.2)

    assert path == home / ".config" / "carbontracker" / "config.toml"
    assert path.exists()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_resolve_overrides_uses_local_config_and_explicit_overrides_win(
    monkeypatch, tmp_path
):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    init_project_config(
        project_name="project-default",
        log_dir="project-logs",
        power_sampling_interval=3.0,
    )

    resolved = resolve_overrides(log_dir="cli-logs")

    assert resolved["project_name"] == "project-default"
    assert resolved["log_dir"] == "cli-logs"
    assert resolved["power_sampling_interval"] == 3.0


def test_cli_init_writes_local_and_global_configs(monkeypatch, tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)

    runner = CliRunner()
    local_result = runner.invoke(cli_module.main, ["init", "--project-name", "demo"])
    global_result = runner.invoke(
        cli_module.main,
        ["init", "--global", "--pue", "1.3", "--api-key", "electricity_maps", "secret"],
    )

    assert local_result.exit_code == 0
    assert get_local_config_file().exists()
    assert global_result.exit_code == 0
    assert get_global_config_file().exists()


def test_cli_replay_uses_project_log_dir_and_allows_explicit_override(
    monkeypatch, tmp_path
):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    init_project_config(project_name="demo", log_dir="project-logs")
    log_line = (
        '{"__type__":"StartedSession","timestamp":"2026-01-01T12:00:00",'
        '"project_name":"demo","run_name":"run-a","log_dir":"project-logs",'
        '"log_file_path":"project-logs/run-a_events.jsonl"}\n'
    )
    (project / "project-logs").mkdir()
    (project / "project-logs" / "run-a_events.jsonl").write_text(log_line)
    (project / "cli-logs").mkdir()
    (project / "cli-logs" / "run-b_events.jsonl").write_text(log_line)

    runner = CliRunner()
    default_result = runner.invoke(cli_module.main, ["replay"])
    override_result = runner.invoke(cli_module.main, ["replay", "cli-logs"])

    assert default_result.exit_code == 0
    assert override_result.exit_code == 0
    assert "[Replay] StartedSession" in default_result.output
    assert "[Replay] StartedSession" in override_result.output
