from multiprocessing.queues import Queue

from src.core.config import ObserverConfig


def create_and_start_observer(
    observer_config: ObserverConfig,
    observation_queue: Queue[ObservationEvent] 
):
    pass