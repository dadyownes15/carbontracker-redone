from dataclasses import dataclass

@dataclass(frozen=True)
class ResolutionStep:
    action: str          # e.g. "provider_resolved", "no_provider"
    detail: str          # human-readable
    level: str           # "info", "warning", "success"
