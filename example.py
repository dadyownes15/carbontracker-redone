import time
from src.tracker import CarbonTracker
from src.core.config import SessionConfig

def main():
    print("Initializing CarbonTracker...")
    # This automatically creates a ManualObserver and necessary DummyProviders
    tracker = CarbonTracker(epochs=2)

    for epoch in range(2):
        print(f"\n--- Starting Epoch {epoch} ---")
        tracker.epoch_start()
        
        # Simulate some heavy compute
        time.sleep(2.5)
        
        tracker.epoch_end()
        print(f"--- Finished Epoch {epoch} ---")

    print("\nStopping tracker...")
    tracker.stop()
    print("Tracking complete!")

if __name__ == "__main__":
    main()
