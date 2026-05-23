from typing import Any, Tuple
from queue import Queue
from core.config import ObserverConfig
import logging

from src.core.events import TrackerEvent
from src.core.execution_guard import ExecutionGuard
from src.data_provider.data_provider import DataProvider
logger = logging.getLogger(__name__)

class TrackerSession:
    """
    Responsbile for generating observation events, such as epoch started, function started, function ended etc.

    """
    def __init__(
        self,
        observer_config: ObserverConfig,
        providers: Tuple[DataProvider[Any]],
        guard: ExecutionGuard,
        event_queue: "Queue[TrackerEvent]", # Outgoing events
        observation_queue: "Queue[Observation]", # Ingoing events
        
    ) -> None:
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("Initializing new tracking session")
        self.providers = providers
        self.guard = guard
        self.event_queue = event_queue
        self.observation_queue = observation_queue
        self.running = False
        
    def start(self):
        try:
            self.event_observer = create_and_start_observer(config=observer_config,observation_queue=self.observation_queue)
            self.running = True
        except
            self.running = False
            raise
        
        self._run()
        
    def _run(self):
        while self.running:
            event = self.observation_queue.get()
            try:
                self.process_event(event)
            finally:
                self.observation_queue.task_done()
                
        
    def process_event(self, observation_event):
        print(f"Processing {observation_event.event_name}")

        # Fetch data from providers if needed
        # 
        # Check gaurd
        # 
        
    def stop(self):
        """Cleanup resources and ensure the process is in a safe state."""
        self.event_observer.stop()
        
        for provider in self.providers:
            if hasattr(provider, 'shutdown'):
                provider.shutdown()