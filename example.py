import time
from carbontracker.entrypoints.programmatic.manual import CarbonTracker
from carbontracker.core.types import Component

def main():
    print("Initializing CarbonTracker...")
    tracker = CarbonTracker(
        epochs=2,
        components=[Component.CPU],
        pue=1.2,
        log_dir="./carbontracker_logs/"
    )

    for epoch in range(2):
        print(f"\n--- Starting Epoch {epoch} ---")
        tracker.epoch_start()

        # Simulate some heavy compute
        time.sleep(5.0)

        tracker.epoch_end()
        print(f"--- Finished Epoch {epoch} ---")

    print("\nStopping tracker...")
    tracker.finish()
    print("Tracking complete!")


if __name__ == "__main__":
    main()
