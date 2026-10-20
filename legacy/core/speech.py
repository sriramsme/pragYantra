import threading
from .utils.aid_speech import Pyttsx3Speech,ElevenLabsSpeech, FacebookMMS
import queue
import sounddevice as sd
import numpy as np
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
import time
from collections import deque
from datetime import datetime
from .hear import LiveTranscriber
from . import MEMORY_STREAM_DIR, verbose_print


class LiveSpeech:
    """
    LiveSpeech class to handle live speech with external speech detection.
    """

    def __init__(self, transcriber:LiveTranscriber, speaker_model=None, audio_monitor=None):
        """
        Initializes the LiveSpeech class.

        Parameters:
            transcriber: The transcriber object for speech-to-text.
            speaker_model (str): The speech synthesis engine to use. Default is None.
            audio_monitor (AudioMonitor): An instance of AudioMonitor. If None, a default one will be created.
        """
        pygame.mixer.init()
        self._setup_speaker(speaker_model)
        
        self._thread = None
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self.transcriber = transcriber
        self._cleanup_thread = threading.Thread(target=self.cleanup)

    def _setup_speaker(self, speaker_model):
        if speaker_model is None or speaker_model == "pyttsx3":
            self._speaker = Pyttsx3Speech()
        elif speaker_model == "11labs":
            self._speaker = ElevenLabsSpeech()
        elif speaker_model == "facebook-mms":
            self._speaker = FacebookMMS()

    def _process_speech(self):
        """
        Process the speech by retrieving text from the queue and saving it to an audio file.
        """
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            save_dir = os.path.join(MEMORY_STREAM_DIR, 'audio_logs/')
            filename = save_dir + datetime.now().strftime("%Y%m%d%H%M%S") + ".wav"

            # Save the speech to an audio file
            self._speaker.save_to_file(filename, text)
            self._play_audio(filename)

    def _play_audio(self, filename):
        """
        Plays the audio file and monitors for external speech.
        """
        pygame.mixer.music.load(filename)
        self.transcriber.pause()
        verbose_print("Pause hearing ability!")

        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if self._stop_event.is_set() or self.transcriber.is_voice_detected():
                pygame.mixer.music.stop()
                break
            time.sleep(0.1)

        time.sleep(0.5)
        
        self.transcriber.resume()
        verbose_print("Resume hearing ability!")

    def start(self):
        """
        Starts the speech processing thread.

        If the speech processing thread is already running, it prints a message and returns.

        Returns:
            None
        """
        if self._thread is not None and self._thread.is_alive():
            print("Speech is already running")
            return

        self._thread = threading.Thread(target=self._process_speech)
        self._thread.start()
        self._cleanup_thread.start()   

        print("Speech thread started")

    def is_speaking(self):
        """
        Checks if the speech is running.

        Returns:
            bool: True if the speech is running, False otherwise.
        """
        return pygame.mixer.music.get_busy()
    
    def speak(self, text):
        """
        Adds the given text to the speech queue.

        Args:
            text (str): The text to be spoken.

        Returns:
            None
        """
        # self.shut_up()
        self._queue.put(text)

    def pause(self):
        """
        Pauses the audio playback.

        Returns:
            None
        """
        pygame.mixer.music.pause()

    def shut_up(self):
        """
        Stops the audio playback.

        Returns:
            None
        """
        pygame.mixer.music.stop()

    def continue_speaking(self):
        """
        Resumes the audio playback.

        Returns:
            None
        """
        pygame.mixer.music.unpause()

    def cleanup(self,sleep_time=20):
        """
        Regularly cleans up the audio logs directory.
        """
        while not self._stop_event.is_set():
            time.sleep(sleep_time)  # Sleep for 20 seconds

            # Delete all files in the directory
            save_dir = os.path.join(MEMORY_STREAM_DIR,'audio_logs/')
            for filename in os.listdir(save_dir):
                file_path = os.path.join(save_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    #if error occured, it most probably means that the file is still being used by speech thread
                    continue
                    # verbose_print(f'Failed to delete {file_path}. Reason: {e}')

    def terminate(self):
        """
        Terminates the speech processing thread and cleans up resources.
        """
        if self._thread is None or not self._thread.is_alive():
            return

        # Stop the audio playback
        pygame.mixer.music.stop()

        # Stop the audio monitor
        # self.audio_monitor.stop_monitoring()

        # Signal the speech processing thread to stop
        self._stop_event.set()

        # Clear the queue to unblock any waiting get() calls
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # Wait for the speech processing thread to finish with a timeout
        self._thread.join(timeout=2.0)
        if self._thread.is_alive():
            print("Warning: Speech processing thread did not terminate in time.")

        # Stop pygame mixer
        pygame.mixer.quit()

        # Perform cleanup
        self.cleanup()
        
        self._cleanup_thread.join()
        # Reset the stop event
        self._stop_event.clear()

        print("Speech thread terminated.")