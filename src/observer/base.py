import queue
from threading import Event, Thread
from src.core.markers import Marker

class BaseObserverThread(Thread):
    def __init__(self, marker_queue: "queue.Queue[Marker]") -> None:
        super().__init__()
        self.marker_queue = marker_queue
        self._stop_event = Event()
        self.daemon = True
    
    def stop(self) -> None:
        self._stop_event.set()

    def manual_start(self) -> None:
        pass

    def manual_end(self) -> None:
        pass

    def run(self) -> None:
        raise NotImplementedError("Subclasses must implement run()")
