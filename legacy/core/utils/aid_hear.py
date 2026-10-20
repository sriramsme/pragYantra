import numpy as np
import sounddevice as sd
import threading
from collections import deque
import time
from datetime import datetime
import whisper
import torch
import os
import re
from .. import verbose_print

class AudioData:
    def __init__(self, sample_rate, buffer_duration=10, vad_window_size=0.096):
        self.sample_rate = sample_rate
        self.buffer_duration = buffer_duration
        self.buffer_size = int(sample_rate * buffer_duration)
        self.samples = deque(maxlen=self.buffer_size)
        self.transcribing_mode_samples = np.array([], dtype=np.float32)
        self.audio_level_db = None
        self.lock = threading.Lock()
        self.vad_window_size = 512 if sample_rate == 16000 else 256

    def add_data(self, data: np.ndarray, transcribing_mode: bool):
        with self.lock:
            # Add data to the circular buffer
            self.samples.extend(data)

            if transcribing_mode:
                # Append data to the transcribing mode buffer
                self.transcribing_mode_samples = np.concatenate((self.transcribing_mode_samples, data))

    def has_enough_for_vad(self,use_transcribing_data=False):
        with self.lock:
            if use_transcribing_data:
                return len(self.transcribing_mode_samples) >= self.vad_window_size
            else:
                return len(self.samples) >= self.vad_window_size
    def get_buffer_data(self):
        with self.lock:
            return np.array(self.samples)

    def get_transcribing_data(self):
        with self.lock:
            return self.transcribing_mode_samples.copy()

    def clear_transcribing_data(self):
        with self.lock:
            self.transcribing_mode_samples = np.array([], dtype=np.float32)

    def get_audio_level(self, use_transcribing_data=False):
        with self.lock:
            data = None
            if use_transcribing_data and len(self.transcribing_mode_samples) > 0:
                data = self.transcribing_mode_samples
            elif len(self.samples) > 0:
                data = np.array(self.samples)
            
            if data is not None:
                epsilon = 1e-10
                return 20 * np.log10(np.abs(data).mean() + epsilon)
            
        return None

    def get_vad_chunks(self,use_transcribing_data=False):
        with self.lock:
            data = np.array(self.samples) if not use_transcribing_data else self.transcribing_mode_samples
            chunks = []
            for i in range(0, len(data) - self.vad_window_size + 1, self.vad_window_size):
                chunk = data[i:i+self.vad_window_size]
                chunks.append(chunk)
            return chunks
        
    def get_silence_duration(self, silence_threshold_db):
        with self.lock:
            data = np.array(self.samples)
            audio_levels = [20 * np.log10(np.abs(chunk).mean() + 1e-10) for chunk in np.array_split(data, 10)]
            silent_chunks = sum(level < silence_threshold_db for level in audio_levels)
            return (silent_chunks / 10) * self.buffer_duration

    def get_transcribing_duration(self):
        with self.lock:
            return len(self.transcribing_mode_samples) / self.sample_rate
        
    def clear_data(self):
        with self.lock:
            self.samples.clear()
            self.transcribing_mode_samples = np.array([], dtype=np.float32)
            self.audio_level_db = None
            self.vad_status = None
            self.eos_status = None

class AudioProcessor:
    def __init__(self, sample_rate=16000, frame_duration=0.5, energy_threshold_db=10, 
                 detection_window=1.0, memory_size=50, buffer_size=30, 
                 model="base", non_english=False,
                 silence_threshold_db=-35, end_of_speech_timeout=1.5,
                 max_silence_ratio=0.8,vad_threshold=0.23):
        # AudioMonitor attributes
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_duration)
        self.energy_threshold_db = energy_threshold_db
        self.detection_window = detection_window
        self.external_speech_detected = threading.Event()
        self.stop_event = threading.Event()
        self.background_energy = None
        self.energy_memory = deque(maxlen=memory_size)
        
        # Transcription attributes
        self.memory_buffer = deque(maxlen=buffer_size)
        self.current_transcription = ""
        self.text_chunks = ""
        self.transcribing_event = threading.Event()
        self.min_audio_length = 2   # Minimum audio length for processing
        self.max_audio_length = 7  # Maximum audio length before forced transcription
        self.max_silence_ratio = max_silence_ratio

        # Shared attributes
        self.stream = None
        self._monitor_thread = None
        self.audio_data = AudioData(sample_rate=self.sample_rate, buffer_duration=5)
        self.speech_history = deque(maxlen=20)
        
        # End of speech detection attributes
        self.end_of_speech_timeout = end_of_speech_timeout
        self.last_speech_time = None
        self.speech_ongoing = False
        self.end_of_speech_detected = threading.Event()
        self.post_speech_wait_time = 1
        self.last_eos_time = None
        self.eos_consecutive_silence_threshold = 5  # Number of consecutive silence frames to trigger EOS
        self.consecutive_silence = 0
        # attributes for silence detection
        self.silence_threshold_db = silence_threshold_db
        self.silence_duration = 0

        # Whisper model
        self.model = model
        self.non_english = non_english
        self.audio_model = self._load_whisper_model()

        # SileroVAD specific attributes
        self.vad_model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                           model='silero_vad',
                                           force_reload=True)
        self.vad_model.eval()
        self.vad_threshold = vad_threshold
        self.vad_window_size = int(sample_rate * 0.096)  # 96ms window for VAD

    def _is_speech(self,use_transcribing_data=False):
        chunks = self.audio_data.get_vad_chunks(use_transcribing_data)
        if not chunks:
            return 0, False

        # Pad chunks to ensure they all have the same length
        max_length = max(len(chunk) for chunk in chunks)
        padded_chunks = [np.pad(chunk, (0, max_length - len(chunk))) for chunk in chunks]

        # Convert padded chunks to a single batch tensor
        batch = torch.from_numpy(np.array(padded_chunks)).float()

        # Move to the same device as the model
        batch = batch.to(next(self.vad_model.parameters()).device)

        # Process the entire batch at once
        with torch.no_grad():
            speech_probs = self.vad_model(batch, self.sample_rate).cpu().numpy()

        avg_speech_prob = speech_probs.mean()
        is_speech = avg_speech_prob > self.vad_threshold
        
        return avg_speech_prob, is_speech

    def _check_eos(self):
        time_since_last_speech = time.time() - self.last_speech_time if self.last_speech_time else 0
       
        return time_since_last_speech > self.end_of_speech_timeout or self.consecutive_silence>=self.eos_consecutive_silence_threshold 


    
    def _extract_speech_segments(self, audio):
        speech_segments = []
        current_segment = []
        is_in_speech = False

        for i in range(0, len(audio), self.vad_window_size):
            chunk = audio[i:i+self.vad_window_size]
            _, is_speech = self._is_speech(chunk)

            if is_speech and not is_in_speech:
                is_in_speech = True
                current_segment = list(chunk)
            elif is_speech and is_in_speech:
                current_segment.extend(chunk)
            elif not is_speech and is_in_speech:
                is_in_speech = False
                if len(current_segment) > self.vad_window_size:  # Minimum segment length
                    speech_segments.append(np.array(current_segment))
                current_segment = []

        if is_in_speech and len(current_segment) > self.vad_window_size:
            speech_segments.append(np.array(current_segment))

        return speech_segments
    def _load_whisper_model(self):
        if self.model != "large" and not self.non_english:
            self.model = self.model + ".en"
        try:
            return whisper.load_model(os.path.join(os.getcwd(), "models", f"{self.model}.pt"))
        except FileNotFoundError:
            return whisper.load_model(self.model)

    def start_processing(self):
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self.stop_event.clear()
            self.external_speech_detected.clear()
            self.transcribing_event.clear()  # Start in transcribing mode
            self._monitor_thread = threading.Thread(target=self._process_audio)
            self._monitor_thread.start()
        return self._monitor_thread

    def stop_processing(self):
        self.stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _set_speech_detected_properties(self,current_time):
        # self.last_speech_time = current_time
        if not self.speech_ongoing:
            self.speech_ongoing = True
            self.end_of_speech_detected.clear()
            self.last_eos_time = None
            self.silence_duration = 0

    def _set_end_of_speech_properties(self,current_time):
        self.last_eos_time = current_time
        self.last_speech_time = self.last_eos_time - self.silence_duration
        if self.speech_ongoing:
            self.speech_ongoing = False
            self.end_of_speech_detected.set()

    def _process_audio(self):
        def audio_callback(indata, frames, time_info, status):
            if status:
                verbose_print(f"Error in audio stream: {status}")
            
            audio_np = indata.flatten().astype(np.float32)
            self.audio_data.add_data(audio_np, self.transcribing_event.is_set())                

        self.stream = sd.InputStream(callback=audio_callback, channels=1, samplerate=self.sample_rate,
                                     blocksize=self.frame_size)

        with self.stream:
            while not self.stop_event.is_set():
                if self.transcribing_event.is_set():
                    self._transcribing_mode()
                else:
                    self._monitoring_mode()

                sd.sleep(200)

    def _monitoring_mode(self):
        current_time = time.time()
        audio_level_db = self.audio_data.get_audio_level(use_transcribing_data=False)

        if audio_level_db is None:
            return  # No audio data available

        # Update background energy
        if self.background_energy is None:
            self.background_energy = audio_level_db
        else:
            self.background_energy = 0.95 * self.background_energy + 0.05 * audio_level_db

        # Update energy memory
        self.energy_memory.append(audio_level_db)
        avg_energy = sum(self.energy_memory) / len(self.energy_memory)

        # Check for speech
        if not self.last_speech_time or current_time - self.last_speech_time > self.detection_window:
            if audio_level_db > self.background_energy + self.energy_threshold_db:
                verbose_print(f"External speech detected! Energy: {audio_level_db:.2f} dB, Avg: {avg_energy:.2f} dB, Background: {self.background_energy:.2f} dB")
                self.external_speech_detected.set()
                self.consecutive_silence = 0
                self._set_speech_detected_properties(current_time)
            else:
                self.external_speech_detected.clear()

    def _transcribing_mode(self):
        audio_level_db = self.audio_data.get_audio_level()
        current_time = time.time()
        transcribe_duration = self.audio_data.get_transcribing_duration()

        # Check for speech using VAD only if we have enough data
        if self.audio_data.has_enough_for_vad():
            speech_prob, vad_is_speech = self._is_speech(use_transcribing_data=True)
        else:
            vad_is_speech = None
            speech_prob = 0
            verbose_print("Not enough data for VAD")

        is_not_silent = audio_level_db > self.silence_threshold_db or vad_is_speech

        # Update speech history and recent speech count
        self.speech_history.append(is_not_silent)
        is_speech_majority = sum(self.speech_history) > len(self.speech_history) * 0.4

        self.consecutive_silence = 0 if is_speech_majority else self.consecutive_silence + 1

        if not self.speech_ongoing:
            if is_speech_majority:
                verbose_print(f"Speech detected: Audio level: {audio_level_db:.2f} dB, VAD prob: {speech_prob:.2f}")
                self._set_speech_detected_properties(current_time)
        elif not self.end_of_speech_detected.is_set():
            if self._check_eos():
                self._set_end_of_speech_properties(current_time)
                verbose_print("End of speech detected.")

        # Check if we should transcribe
        if self.end_of_speech_detected.is_set() and transcribe_duration > self.min_audio_length:
            enough_time_since_last_eos = self.last_eos_time and (current_time - self.last_eos_time) > self.post_speech_wait_time

            if enough_time_since_last_eos or transcribe_duration > self.max_audio_length:
                verbose_print(f"Transcribing. Duration: {transcribe_duration:.2f}s")
                self._transcribe()
        
        elif not is_speech_majority and transcribe_duration > self.max_audio_length*3:
            verbose_print(f"Max duration reached. Clearing buffer. Duration: {transcribe_duration:.2f}s")
            self.audio_data.clear_transcribing_data()

    def _transcribe(self):
        transcribe_audio = self.audio_data.get_transcribing_data()

        result = self.audio_model.transcribe(transcribe_audio, fp16=torch.cuda.is_available())
        transcribed_text = result['text'].strip()
        
        if self.is_valid_text(transcribed_text):
            self.text_chunks += transcribed_text + " "
            self._complete_current_phrase()

        # Clear the transcribing buffer after transcription
        self.audio_data.clear_transcribing_data()
    
    @staticmethod
    def is_valid_text(text):
        pattern = r"^(?! *[\., ]*$).+"
        return bool(re.match(pattern, text))
    
    
    def _adjust_silence_threshold(self):
        silence_threshold_adjustment_rate = 0.05
        if len(self.background_silence_levels) > 0:
            avg_silence_level = sum(self.background_silence_levels) / len(self.background_silence_levels)
            # Adjust the silence threshold
            self.silence_threshold_db = (1 - silence_threshold_adjustment_rate) * self.silence_threshold_db + \
                                        silence_threshold_adjustment_rate * (avg_silence_level + 5)  # 5 dB buffer


    def _complete_current_phrase(self):
        completed_phrase = self.text_chunks.strip()
        if completed_phrase:
            self.memory_buffer.append((datetime.now(), completed_phrase))
            self.current_transcription += completed_phrase + " "
            verbose_print(f"Phrase completed: {completed_phrase}")
            self.text_chunks = ""

    def is_ready_for_processing(self):
        """
        Returns True if ready for processing transcript.
        If the end of speech is detected and the post-speech wait time has elapsed, return True.
        """
        return self.current_transcription and self.last_eos_time and (time.time()-self.last_eos_time)>self.post_speech_wait_time

    def pause_transcription(self):
        """Pause transcription and start monitoring for external speech"""
        self.transcribing_event.clear()
        self.external_speech_detected.clear()

    def resume_transcription(self):
        """Resume transcription and stop monitoring for external speech"""
        self.transcribing_event.set()
        self.external_speech_detected.clear()
        self.speech_ongoing = False
        self.end_of_speech_detected.clear()
        verbose_print("Transcription resumed")

    def force_complete_phrase(self):
        """Force completion of the current phrase"""
        self._complete_current_phrase()

    
    def is_end_of_speech(self):
        """Check if end of speech is detected"""
        return self.end_of_speech_detected.is_set()

    def wait_for_end_of_speech(self, timeout=None):
        """Wait for the end of speech to be detected"""
        return self.end_of_speech_detected.wait(timeout)

    def get_recent_context(self, relevance_threshold=300):
        now = datetime.now()
        recent_transcriptions = [
            text for timestamp, text in self.memory_buffer
            if (now - timestamp).total_seconds() <= relevance_threshold
        ]
        return " ".join(recent_transcriptions)

    def is_external_speech_detected(self):
        return self.external_speech_detected.is_set()

