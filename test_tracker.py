import time
import logging
from src.tracker import CarbonTracker
from src.core.config import SessionMode

def main():
    tracker = CarbonTracker(
        epochs=1,
        components="cpu",
        log_dir="./test_logs",
        log_file_prefix="test",
        verbose=1
    )
    
    tracker.epoch_start()
    time.sleep(1)
    tracker.epoch_end()
    
    stats = tracker.finish()
    print("Returned stats:", stats)

if __name__ == "__main__":
    main()
