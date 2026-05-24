from datetime import datetime
from typing import Optional
import queue

from src.core.markers import Marker
from src.observer.base import BaseObserverThread

class PythonObserverThread(BaseObserverThread):
    def __init__(self, marker_queue: "queue.Queue[Marker]") -> None:
        super().__init__(marker_queue)
        self._current_epoch = 0
        self._current_span_id: Optional[str] = None

    def manual_start(self) -> None:
        self._current_epoch += 1
        self._current_span_id = f"epoch_{self._current_epoch}"
        marker = Marker(
            timestamp=datetime.now(),
            span_id=self._current_span_id,
            context={"event": "start", "epoch": self._current_epoch}
        )
        self.marker_queue.put(marker)

    def manual_end(self) -> None:
        if not self._current_span_id:
            return  
            
        marker = Marker(
            timestamp=datetime.now(),
            span_id=self._current_span_id,
            context={"event": "end", "epoch": self._current_epoch}
        )
        self.marker_queue.put(marker)
        self._current_span_id = None

    def run(self) -> None:
        self._stop_event.wait()
