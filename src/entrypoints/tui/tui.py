from pathlib import Path


def tui_watch(log_dir: str):
    """
    Bare minimum TUI watch entry point.
    Future: uses Textual or Rich Live to display a dashboard.

    The TUI is a pure read-only consumer of the log files written by
    the FileWriterThread. It never touches the engine directly.
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        print(f"No logs found at {log_path}")
        return

    print(f"[TUI Placeholder] Watching logs at: {log_path}")
    print("[TUI Placeholder] Future: Rich/Textual live dashboard here")
    # Future implementation:
    # - Read JSONL log files from log_dir
    # - Parse TrackerEvents
    # - Render live dashboard with energy, emissions, predictions


def tui_init_wizard():
    """
    Bare minimum TUI init wizard entry point.
    Future: interactive prompts for API keys, location, components.
    """
    print("[TUI Placeholder] Future: interactive setup wizard here")
    # Future implementation:
    # - Prompt for electricityMaps API key → save to GlobalConfig
    # - Prompt for default location → save to GlobalConfig
    # - Prompt for project-specific components → save to LocalConfig
    # - Auto-append .carbontracker/ to .gitignore
