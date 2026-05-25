import queue
from threading import Event, Thread
from src.core.markers import Marker

class ObserverThread(Thread):
    def __init__(self, marker_queue: "queue.Queue[Marker]", name: str) -> None:
        super().__init__()
        self.marker_queue = marker_queue
        self._stop_event = Event()
        self.daemon = True
        self.name = name + "observer"
    
    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        raise NotImplementedError("Subclasses must implement run()")
