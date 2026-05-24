

from typing import Any, Dict, Literal
from pydantic.dataclasses import dataclass
from datetime import datetime

from typing_extensions import Optional


@dataclass(frozen=True)
class Marker:
    marker_id: str
    trace_id: str         # The overarching session/run ID (Stays the same for the whole script)
    span_id: str          # The ID of THIS specific block (epoch, function, etc.)
    parent_span_id: str   # The ID of the block that wraps this one (None if root)
    timestamp: datetime
    tags: Optional[Dict[str, str]] = None  # Standardized metadata


class EpochMarker:



    factory:

        (epoch_current,start or end)