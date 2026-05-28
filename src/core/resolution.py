from dataclasses import dataclass

@dataclass(frozen=True)
class ResolutionStep:
    action: str          # e.g. "provider_resolved", "no_provider"
    detail: str          # human-readable
    level: str           # "info", "warning", "success"

import logging

def print_resolution_steps(steps: list[ResolutionStep], logger: logging.Logger) -> None:
    """Prints the resolution steps using the provided logger."""
    for step in steps:
        if step.level == "success":
            logger.info(f"✓ {step.detail}")
        elif step.level == "warning":
            logger.warning(f"⚠ {step.detail}")
        else:
            logger.info(f"ℹ {step.detail}")
