import json
from queue import Queue
from threading import Thread
from pathlib import Path
from datetime import datetime
from enum import Enum
import dataclasses

from src.core.events import TrackerEvent

class EventJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        # Handle pydantic models or other objects if necessary
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return super().default(obj)

class FileLoggerThread(Thread):
    def __init__(self, log_dir: str, run_name: str, event_queue: Queue[TrackerEvent]): 
        super().__init__()
        self.log_dir = log_dir
        self.run_name = run_name
        self.event_queue = event_queue
        self.name = "File Logger Thread"
        
        # Making it a daemon thread ensures it automatically shuts down 
        # when your main application exits
        self.daemon = True
        
        log_dir_path = Path(self.log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        run_name = self.run_name if self.run_name else "carbontracker"
        self.log_file_path = log_dir_path / f"{run_name}_events.jsonl"

    def stop(self) -> None:
        self.event_queue.put(None)

    def run(self) -> None:
        """Continuously monitors the queue and writes full events to a JSONL file."""
        with open(self.log_file_path, "a") as log_file:
            while True:
                event = self.event_queue.get()

                # Close signal
                if event is None:
                    self.event_queue.task_done()
                    break
                    
                try:
                    # Inject event type for easier parsing
                    event_dict = dataclasses.asdict(event)
                    event_dict["__type__"] = type(event).__name__
                    
                    json_str = json.dumps(event_dict, cls=EventJSONEncoder)
                    log_file.write(json_str + "\n")
                    log_file.flush()
                except Exception as e:
                    # Fallback or silent failure for logging errors to not block application
                    pass
                finally:
                    # Tell the queue that processing for this item is complete
                    self.event_queue.task_done()
