import time
import sys

def simulate_training():
    print("Starting training script...", flush=True)
    
    # Outer span (Epoch 1)
    print("carbontracker:epoch_1:start", flush=True)
    time.sleep(0.5)
    
    # Nested inner span (Batch 1)
    print("carbontracker:batch_1:start", flush=True)
    time.sleep(0.5)
    print("carbontracker:batch_1:end", flush=True)
    
    # Nested inner span (Batch 2)
    print("carbontracker:batch_2:start", flush=True)
    time.sleep(0.5)
    print("carbontracker:batch_2:end", flush=True)
    
    # Close outer span
    print("carbontracker:epoch_1:end", flush=True)
    print("Training complete.", flush=True)

if __name__ == "__main__":
    simulate_training()
