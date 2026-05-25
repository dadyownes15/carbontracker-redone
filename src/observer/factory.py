import queue
from typing import Dict, Callable, List
from threading import Event

from src.core.config import ObserverConfig
from src.core.events import TrackerEvent
from src.observer.base import ObserverThread
from src.observer.providers.manual import ManualObserverThread

def _create_manual(aq: "queue.Queue[TrackerEvent]", es: "List[queue.Queue[TrackerEvent]]", ne: List[Event]) -> ObserverThread:
    return ManualObserverThread(aq, es, ne)

CREATORS: Dict[str, Callable[["queue.Queue[TrackerEvent]", "List[queue.Queue[TrackerEvent]]", List[Event]], ObserverThread]] = {
    "python-manual": _create_manual,
}

def observer_factory(
    config: ObserverConfig, 
    aggregation_queue: "queue.Queue[TrackerEvent]",
    event_sink: "List[queue.Queue[TrackerEvent]]",
    notify_events: List[Event]
) -> ObserverThread:
    if config.type not in CREATORS:
        raise ValueError(f"Unknown observer type: {config.type}")
    return CREATORS[config.type](aggregation_queue, event_sink, notify_events)
