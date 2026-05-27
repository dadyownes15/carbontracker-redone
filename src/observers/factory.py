import queue
from typing import Dict, Callable, List
from threading import Event

from src.config.config import ObserverConfig, SessionMode
from src.core.events import TrackerEvent
from src.observers.base import ObserverThread
from src.observers.providers.manual import ManualObserverThread

def observer_factory(
    config: ObserverConfig, 
    mode: SessionMode,
    aggregation_queue: "queue.Queue[TrackerEvent]",
    event_sink: "List[queue.Queue[TrackerEvent]]",
    notify_events: List[Event]
) -> ObserverThread:
    
    if mode == SessionMode.PYTHON_API:
        return ManualObserverThread(aggregation_queue, event_sink, notify_events)
    elif mode == SessionMode.PYTHON_DECORATOR:
        raise NotImplementedError("python-decorator mode is not yet implemented")
    elif mode == SessionMode.SUBPROCESS:
        raise NotImplementedError("subprocess mode is not yet implemented")
    else:
        raise ValueError(f"Unknown observer mode: {mode}")



