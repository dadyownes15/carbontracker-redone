# Events are processing events from generate from the event observer
from datetime import datetime
from typing import Any, Dict, Generic

from pydantic.dataclasses import dataclass
from pydantic import ConfigDict
from src.data_provider.data_provider import TData, DataProvider

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
    
@dataclass(frozen=True)
class EventStart(TrackerEvent):    
    started_at: datetime 
    span_id: str

@dataclass(frozen=True)
class EventStats(TrackerEvent):
    span_id: str
    started_at: datetime
    ended_at: datetime
    data: Dict[str,Any]
    
    
@dataclass(frozen=True)
class PredictionEvent(TrackerEvent):    
    created_at: datetime 
    span_id: str
    # We need some data model for the prediction results

@dataclass(frozen=True)
class GaurdEvent(TrackerEvent):
    pass
            
@dataclass(frozen=True)
class FinishedSession(TrackerEvent):
    pass
    
@dataclass(frozen=True)
class StartedSession(TrackerEvent):
    pass
     