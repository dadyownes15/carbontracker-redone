from threading import Thread, Event
from typing import List, TypeVar, Generic
from src.data_provider.data_provider import DataProvider, MeasurementData

TData = TypeVar('TData', bound=MeasurementData)

class DataProviderThread(Thread, Generic[TData]):
    """
    Statically typed, autonomous base provider thread.
    """
    def __init__(self, sample_interval: float, providers: List[DataProvider[TData]], measurements: List[TData]) -> None:
        super().__init__()
        self.sample_interval = sample_interval
        self.providers = providers
        self.measurements = measurements
        self._trigger_event = Event()
        self._stop_event = Event()
        self._fetch_done_event = None
        self.daemon = True
        self.name: str =  "_".join([provider.name for provider in self.providers])

    def trigger_fetch(self) -> Event:
        """Wakes up the thread to do an immediate fetch and returns a completion event."""
        self._fetch_done_event = Event()
        self._trigger_event.set()
        return self._fetch_done_event

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
            
            if self._fetch_done_event:
                self._fetch_done_event.set()
                self._fetch_done_event = None

    def _work(self) -> None:
        for provider in self.providers:
            measurement = provider.fetch()
            self.measurements.append(measurement)


