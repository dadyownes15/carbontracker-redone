import queue
from typing import Dict, Callable

from src.core.config import ObserverConfig
from src.core.markers import Marker
from src.observer.base import ObserverThread
from src.observer.providers.manual import ManualObserverThread

CREATORS: Dict[str, Callable[["queue.Queue[Marker]"], ObserverThread]] = {
    "python-manual": lambda mq: ManualObserverThread(mq),
}

def observer_factory(config: ObserverConfig, marker_queue: "queue.Queue[Marker]") -> ObserverThread:
    if config.type not in CREATORS:
        raise ValueError(f"Unknown observer type: {config.type}")
    return CREATORS[config.type](marker_queue)
