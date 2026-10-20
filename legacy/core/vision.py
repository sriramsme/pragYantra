import threading
from .utils.aid_vision import VisionAid

class LiveVision:
    """
    Vision class to handle all vision related tasks
    """
    def __init__(self):
        """
        Constructor
        """
        self._aid = VisionAid(stop_event_wait_time=30, save_to_json_interval=3)
        self._thread = None
        self._stop_event = threading.Event()
        self.previous_context = ""

    def start(self):
        """
        Starts the vision thread if it is not already running.
        """
        if self._thread is not None and self._thread.is_alive():
          print("Vision is already running")
          return
        self._aid.set_blind(False)
        self._thread = threading.Thread(target=self._aid.get_visual_context, args=(self._stop_event,))
        self._thread.start()

        print("Vision thread started")

    def get_previous_current_context(self):
        """
        Get the previous and current context.

        Returns:
            tuple: A tuple containing the previous and current context.
        """
        previous_context = self.previous_context
        current_context = self._aid.current_seen
        
        # Update previous context with current value
        self.previous_context = current_context
        
        # Clear current context
        self._aid.current_seen = ""
        
        return previous_context, current_context

    def terminate(self):
        """
        Stops the vision thread if it is running.
        """
        if self._thread is None or not self._thread.is_alive():
            return
        self._aid.set_blind(True)
        # Signal the Vision thread to stop
        self._stop_event.set()

        # Wait for the Vision thread to finish
        self._thread.join(timeout=3.0)

        # Reset the stop event so we can start the Vision again
        self._stop_event.clear()
        
        print("Vision thread stopped.")






