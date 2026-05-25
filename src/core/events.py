# Events are processing events from generate from the event observer
from datetime import datetime
from typing import Any, Dict, Generic, Optional

from enum import Enum
from pydantic.dataclasses import dataclass
from pydantic import ConfigDict
from src.data_provider.data_provider import TData 
from src.core.markers import Marker
from src.core.stats import EventStatsData, SessionStatsData, SessionFinalStats
class LogSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class TrackerEvent():
    ...
    

@dataclass(frozen=True, config=ConfigDict(arbitrary_types_allowed=True))
class MeasurementEvent(TrackerEvent, Generic[TData]):
    provider_name: str 
    timestamp: datetime
    data: TData 
    
@dataclass(frozen=True)
class EventStop(TrackerEvent):    
    ended_at: datetime
    span_id: str
    span_type: str = "epoch"
    parent_span_id: Optional[str] = None
    
@dataclass(frozen=True)
class EventStart(TrackerEvent):    
    started_at: datetime 
    span_id: str
    span_type: str = "epoch"
    parent_span_id: Optional[str] = None

@dataclass(frozen=True)
class EventStats(TrackerEvent):
    span_id: str
    started_at: datetime
    ended_at: datetime
    stats: EventStatsData
    
@dataclass(frozen=True)
class SessionCurrentStatsEvent(TrackerEvent):
    timestamp: datetime
    stats: SessionStatsData

@dataclass(frozen=True)
class PredictionEvent(TrackerEvent):    
    created_at: datetime 
    span_id: str
    result: Any # Using Any to avoid circular import with prediction.py, or we can import it. Wait, let's just use Any for now or TYPE_CHECKING.

@dataclass(frozen=True)
class GuardEvent(TrackerEvent):
    created_at: datetime
    verdict: Any
    prediction: Any

@dataclass(frozen=True)
class DiagnosticEvent(TrackerEvent):
    severity: LogSeverity
    message: str
    logger_name: str
    timestamp: datetime

            
@dataclass(frozen=True)
class FinishedSession(TrackerEvent):
    timestamp: datetime
    stats: SessionFinalStats
    
@dataclass(frozen=True)
class StartedSession(TrackerEvent):
    pass
     