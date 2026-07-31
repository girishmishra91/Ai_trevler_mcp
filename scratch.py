import sys
import tracking
import traceback

print("Testing track_flight:")
try:
    print(tracking.track_flight("AI202"))
except Exception as e:
    traceback.print_exc()

print("Testing get_train_tracker_info:")
try:
    print(tracking.get_train_tracker_info("London", "Manchester"))
except Exception as e:
    traceback.print_exc()

