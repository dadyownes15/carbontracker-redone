from threading import Thread
from typing import Any, Tuple
from queue import Queue
from core.config import ObserverConfig
import logging

from src.core.events import TrackerEvent
from src.core.execution_guard import ExecutionGuard
from src.core.markers import Marker
from src.data_provider.data_provider import DataProvider
logger = logging.getLogger(__name__)

class TrackerThread(Thread):
    """
    Responsbile for generating observation events, such as epoch started, function started, function ended etc.

    """
    def __init__(
        self,
        observer_config: ObserverConfig,
        marker_queue: "Queue[Marker]", # Ingoing events
        
    ) -> None:
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("Initializing new tracking session")
        self.marker_queue = marker_queue
        self.running = False

        
        # Create threead here based on the observer_onifg
        
        # We also need some kind of marker object, that creates the marker
    def start(self):
        try:
            self.event_observer = create_and_start_observer(config=observer_config,marker_queue=self.marker_queue)
            # self.measurement_threads = 
            self.running = True
        except Exception:
            self.running = False
            raise
        
        self._run()
        
    def start_epoch(self):
        ...

    def end_epoch(self):
        ...
       