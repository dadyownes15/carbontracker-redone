import queue
from threading import Thread, Event
from typing import List, TypeVar, Generic
from src.data_provider.data_provider import DataProvider, MeasurementData
from src.core.events import TrackerEvent, MeasurementEvent

TData = TypeVar('TData', bound=MeasurementData)

class DataProviderThread(Thread, Generic[TData]):
    """
    Statically typed, autonomous base provider thread.
    """
    def __init__(self, sample_interval: float, providers: List[DataProvider[TData]], aggregation_queue: "queue.Queue[TrackerEvent]", notify_event: Event) -> None:
        super().__init__()
        self.sample_interval = sample_interval
        self.providers = providers
        self.aggregation_queue = aggregation_queue
        self._trigger_event = notify_event
        self._stop_event = Event()
        self.daemon = True
        self.name: str =  "_".join([provider.name for provider in self.providers])

    def stop(self) -> None:
        self._stop_event.set()
        self._trigger_event.set()

    def run(self) -> None:
        self._work()
        while not self._stop_event.is_set():
            # Blocks until sample_interval passes (in-between fetch) OR trigger_event is set (forced fetch)
            self._trigger_event.wait(timeout=self.sample_interval)
            
            if self._stop_event.is_set():
                break
                
            self._trigger_event.clear()
            self._work()

    def _work(self) -> None:
        for provider in self.providers:
            measurement = provider.fetch()
            event = MeasurementEvent(
                provider_name=provider.name,
                timestamp=measurement.timestamp,
                data=measurement,
            )
            self.aggregation_queue.put(event)

