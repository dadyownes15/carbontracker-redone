import queue
from typing import Dict, Callable

from src.core.config import ObserverConfig
from src.core.markers import Marker
from src.observer.base import BaseObserverThread
from src.observer.providers.manual import ManualObserverThread

CREATORS: Dict[str, Callable[["queue.Queue[Marker]"], BaseObserverThread]] = {
    "manual": lambda mq: ManualObserverThread(mq),
}

def observer_factory(config: ObserverConfig, marker_queue: "queue.Queue[Marker]") -> BaseObserverThread:
    if config.type not in CREATORS:
        raise ValueError(f"Unknown observer type: {config.type}")
    return CREATORS[config.type](marker_queue)
