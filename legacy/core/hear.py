import threading
from .utils.aid_hear import AudioProcessor

class LiveTranscriber:
    """
    LiveTranscriber class to handle live transcription.

    Methods:
    - __init__(): Initializes the LiveTranscriber object.
    - start(): Starts the live transcription process.
    - terminate(): Terminates the live transcription process.
    """

    def __init__(self):
      self._stop_event = threading.Event()
      self._aid = AudioProcessor(model="base")
      self.previous_transcription = ""

    def start(self):
      """
      Starts the live transcription process.

      If the transcription is already running, it prints a message and returns.
      Otherwise, it creates a new thread and starts the live_transcribe function.
      """

      self._aid.start_processing()
      print("Transcribing thread started.")

    def get_previous_current_transcription(self):
      """
      Get the previous and current transcription.

      Returns:
          tuple: A tuple containing the previous and current transcription.
      """
      previous_transcription = self.previous_transcription
      current_transcription = self._aid.current_transcription
      
      # Update previous transcription with current value
      self.previous_transcription = current_transcription
      
      # Clear current transcription
      self._aid.current_transcription = ""
      
      return previous_transcription, current_transcription

    def is_voice_detected(self):
        """
        Checks if anyone is talking/ voice activity detection (VAD).

        Returns:
            bool: True if vad, False otherwise.
        """
        return self._aid.external_speech_detected.is_set()
    

    def is_listening(self):
       return self._aid.transcribing_event.is_set()
    
    def pause(self):
        """
        Pause transcription.
        """
        self._aid.pause_transcription()

    def resume(self):
        """
        Resume transcription.
        """
        self._aid.resume_transcription()

    def terminate(self):
      """
      Terminates the live transcription process.

      If the transcription is not running, it prints a message and returns.
      Otherwise, it signals the transcription thread to stop, waits for it to finish,
      and resets the stop event so that transcription can be started again.
      """
      # if self._thread is None or not self._thread.is_alive():
      #   print("Transcriber is not running")
      #   return

      self._aid.stop_processing()
      # Signal the transcription thread to stop
      self._stop_event.set()

      # Wait for the transcription thread to finish
      # self._thread.join(timeout=1.0)

      # Reset the stop event so we can start the transcription again
      self._stop_event.clear()
      print("Hearing thread stopped.")


if __name__ == "__main__":
    transcriber = LiveTranscriber()
    transcriber.start()
    print("Transcriber started.")
