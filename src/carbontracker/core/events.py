from datetime import datetime
from typing import Any, Generic 

from enum import Enum
from pydantic.dataclasses import dataclass
from pydantic import ConfigDict
from carbontracker.providers.data_provider import TData 
from carbontracker.core.stats import SpanStats, SessionStatsData, SessionFinalStats

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
class SpanStop(TrackerEvent):    
    ended_at: datetime
    span_id: str
    parent_span_id: str | None = None
    trace_id: str | None = None
    
@dataclass(frozen=True)
class SpanStart(TrackerEvent):    
    started_at: datetime 
    span_id: str
    parent_span_id: str | None = None
    trace_id: str | None = None

@dataclass(frozen=True)
class SpanProfileEvent(TrackerEvent):
    created_at: datetime
    span_id: str
    parent_span_id: str | None
    started_at: datetime
    ended_at: datetime
    profile: Any
    stats: SpanStats | None = None 
    
@dataclass(frozen=True)
class SessionCurrentStatsEvent(TrackerEvent):
    timestamp: datetime
    stats: SessionStatsData

@dataclass(frozen=True)
class PredictionEvent(TrackerEvent):    
    created_at: datetime 
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
     
