from queue import Queue
from threading import Thread

from src.core.events import TrackerEvent


class WriterThread(Thread):
    def __init__(self, event_queue: Queue[TrackerEvent]): 
        super().__init__()
        self.event_queue = event_queue
        
        # Making it a daemon thread ensures it automatically shuts down 
        # when your main application exits
        self.daemon = True

    def stop(self) -> None:
        self.event_queue.put(None)

    def run(self) -> None:
        """Continuously monitors the queue and prints incoming events."""
        while True:
            # .get() blocks automatically until an item is available
            event = self.event_queue.get()
            
            # Optional: Check for a "poison pill" (None) to cleanly shut down if needed
            if event is None:
                self.event_queue.task_done()
                break
                
            # Print out the event
            print(f"[WriterThread] Processing Event: {event}")
            
            # Tell the queue that processing for this item is complete
            self.event_queue.task_done()