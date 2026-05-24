from datetime import datetime
from typing import Optional
import queue
import uuid

from src.core.markers import Marker
from src.observer.base import BaseObserverThread

class ManualObserverThread(BaseObserverThread):
    def __init__(self, marker_queue: "queue.Queue[Marker]") -> None:
        super().__init__(marker_queue)
        self._current_epoch = 0
        self._current_span_id: Optional[str] = None
        self._trace_id = str(uuid.uuid4())

    def manual_start(self) -> None:
        self._current_epoch += 1
        self._current_span_id = f"epoch_{self._current_epoch}"
        marker = Marker(
            marker_id=str(uuid.uuid4()),
            trace_id=self._trace_id,
            parent_span_id=None,
            timestamp=datetime.now(),
            span_id=self._current_span_id,
            tags={"event": "start", "epoch": str(self._current_epoch)}
        )
        self.marker_queue.put(marker)

    def manual_end(self) -> None:
        if not self._current_span_id:
            return  
            
        marker = Marker(
            marker_id=str(uuid.uuid4()),
            trace_id=self._trace_id,
            parent_span_id=None,
            timestamp=datetime.now(),
            span_id=self._current_span_id,
            tags={"event": "end", "epoch": str(self._current_epoch)}
        )
        self.marker_queue.put(marker)
        self._current_span_id = None

    def run(self) -> None:
        self._stop_event.wait()
