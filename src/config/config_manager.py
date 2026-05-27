import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import tomli
import tomli_w
from pydantic import BaseModel, Field

from src.core.types import Location
from src.config.default_config import TrackDefaults

GLOBAL_CONFIG_DIR = Path.home() / ".config" / "carbontracker"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.toml"
LOCAL_CONFIG_DIR = Path(".carbontracker")
LOCAL_CONFIG_FILE = LOCAL_CONFIG_DIR / "config.toml"


class GlobalConfig(BaseModel):
    """
    Stored at ~/.config/carbontracker/config.toml (chmod 600).
    """
    api_keys: Dict[str, str] = Field(default_factory=dict)
    default_location: Optional[Location] = None
    default_pue: Optional[float] = None


class ResolvedConfig(BaseModel):
    """Output of the resolution pipeline: a TrackDefaults + secrets."""
    defaults: TrackDefaults
    api_keys: Dict[str, str]


def _read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomli.load(f)
    except Exception as e:
        import logging
        logging.getLogger("carbontracker").warning(f"Failed to read {path}: {e}")
        return {}


def _write_toml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def load_global_config() -> GlobalConfig:
    data = _read_toml(GLOBAL_CONFIG_FILE)
    try:
        return GlobalConfig.model_validate(data)
    except Exception:
        return GlobalConfig()


def save_global_config(config: GlobalConfig) -> None:
    data = config.model_dump(exclude_none=True)
    _write_toml(GLOBAL_CONFIG_FILE, data)
    # Enforce strict 600 permissions for secure API key storage
    try:
        os.chmod(GLOBAL_CONFIG_FILE, 0o600)
    except Exception:
        pass


def load_local_config() -> Dict[str, Any]:
    return _read_toml(LOCAL_CONFIG_FILE)


def save_local_config(config: TrackDefaults) -> None:
    data = config.model_dump(exclude_none=True)
    _write_toml(LOCAL_CONFIG_FILE, data)

    # Safely append to .gitignore
    gitignore = Path(".gitignore")
    if gitignore.exists():
        content = gitignore.read_text()
        if ".carbontracker/" not in content and ".carbontracker" not in content:
            with open(gitignore, "a") as f:
                f.write("\n# CarbonTracker Local Configuration\n.carbontracker/\n")
    else:
        with open(gitignore, "w") as f:
            f.write("# CarbonTracker Local Configuration\n.carbontracker/\n")


def resolve_config(overrides: TrackDefaults) -> ResolvedConfig:
    """
    Resolution pipeline:
    1. Base TrackDefaults
    2. Overlay GlobalConfig (PUE, Location)
    3. Overlay LocalConfig
    4. Overlay Env Vars (TODO)
    5. Overlay overrides (TrackDefaults)
    """
    global_cfg = load_global_config()
    local_cfg = load_local_config()

    # Create a fresh defaults object
    defaults = TrackDefaults()

    # 1. Apply Global Config
    if global_cfg.default_pue is not None:
        defaults.pue = global_cfg.default_pue
    if global_cfg.default_location is not None:
        defaults.location = global_cfg.default_location

    # 2. Apply Local Config
    if local_cfg:
        defaults = defaults.model_copy(update=local_cfg)

    # 3. Apply Environment Variables (Example for future)
    if "CARBONTRACKER_API_KEY" in os.environ:
        global_cfg.api_keys["electricityMaps"] = os.environ["CARBONTRACKER_API_KEY"]
    if "CARBONTRACKER_PUE" in os.environ:
        try:
            defaults.pue = float(os.environ["CARBONTRACKER_PUE"])
        except ValueError:
            pass

    # 4. Apply user overrides
    # We only want to override fields that were explicitly set by the user,
    # but Pydantic BaseModel doesn't track "is_set". 
    # Since overrides is passed in fully formed, it acts as the final truth.
    # However, to merge properly, we should overlay `defaults` with `overrides.model_dump(exclude_unset=True)`.
    # Wait, `overrides` was instantiated with `TrackDefaults(**kwargs)`, so exclude_unset=True works!
    merged = defaults.model_copy(update=overrides.model_dump(exclude_unset=True))

    return ResolvedConfig(
        defaults=merged,
        api_keys=global_cfg.api_keys
    )
