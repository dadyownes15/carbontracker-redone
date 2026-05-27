import time
import logging
from src.entrypoints.programmatic.manual import CarbonTracker
from src.core.types import Component

def main():
    tracker = CarbonTracker(
        epochs=1,
        components=[Component.CPU],
        log_dir="./test_logs",
        project_name="test"
    )
    
    tracker.epoch_start()
    time.sleep(1)
    tracker.epoch_end()
    
    stats = tracker.finish()
    print("Returned stats:", stats)

if __name__ == "__main__":
    main()
