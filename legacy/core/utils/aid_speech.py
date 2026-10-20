import pyttsx3
import os
from .. import MODELS_DIR, ENV_PATH

class Speech:
    """
    Speech class to handle all speech related tasks
    """
    def __init__(self):
        """
        Constructor
        """
        pass

    def speak_instant(self, text):
        raise NotImplementedError("Subclass must implement text_to_speech method")

    def save_to_file(self, filename, text):
        raise NotImplementedError("Subclass must implement save_to_file method")

class Pyttsx3Speech(Speech):
    """
    A class that provides text-to-speech functionality using the pyttsx3 library.

    Attributes:
        speech_engine (pyttsx3.Engine): The pyttsx3 speech engine.
        speech_rate (int): The speech rate in words per minute.

    Methods:
        text_to_speech(text): Converts the given text to speech.
        save_to_file(filename, text): Saves the given text to a file.
        play(): Plays the speech.
        set_speech_rate(rate): Sets the speech rate to the specified value.
        get_speech_rate(): Returns the current speech rate.
        set_speech_voice(voice): Sets the speech voice to the specified value.
        get_speech_voices(): Returns the available speech voices.
    """

    def __init__(self):
        super().__init__()
        self.speech_engine = pyttsx3.init()
        self.speech_engine.setProperty('rate', 190)

    def speak_instant(self,text:str):
        self.speech_engine.say(text)
        self.speech_engine.runAndWait()

    def text_to_speech(self, text:str):
        # Implementation for pyttsx3 goes here
        self.speech_engine.say(text)
    
    def save_to_file(self, filename:str, text:str):
        self.speech_engine.save_to_file(text, filename)
        self.speech_engine.runAndWait()

    def play(self):
        self.speech_engine.runAndWait()

    def stop(self):
        self.speech_engine.stop()

    def set_speech_rate(self,rate):
        self.speech_rate=rate
        self.speech_engine.setProperty('rate', rate)

    def get_speech_rate(self):
        return self.speech_rate
    
    def set_speech_voice(self, voice_id):
        """
        Set the voice for the speech engine.

        :param voice_id: The ID of the voice to use.
        """
        self.speech_engine.setProperty('voice', voice_id)


    def get_speech_voices(self):
        """
        Get ids of all voices available on your machine.

        :return: A dictionary where the keys are the indices and the values are the voice objects.
        """
        voices = {}
        for i, voice in enumerate(self.speech_engine.getProperty('voices')):
            voices[i] = voice.id
        return voices

    def set_volume(self, volume):
        """
        Set the volume of the speech engine. only between 0 and 1

        :param volume: The volume to set.
        """
        if not 0 <= volume <= 1:
            raise ValueError("Volume must be between 0 and 1")

        self.speech_engine.setProperty('volume', volume)

    def get_volume(self):
        """
        Get the current volume of the speech engine.

        :return: The current volume.
        """
        return self.speech_engine.getProperty('volume')

import requests

from pydub import AudioSegment
from pydub.playback import play
import io
import time
from dotenv import load_dotenv
load_dotenv(ENV_PATH)

class ElevenLabsSpeech(Speech):
    """
    A class that provides text-to-speech functionality using the Eleven Labs API.
    """
    def __init__(self):
        """
        
        """
        super().__init__()
        print("Add a speech key to the env file in root directory")
    def __get_response(self, text):
        """
        This method converts text to audio using Eleven Labs API.
        
        Args:
            text (str): The text to be converted to audio.
        
        Returns:
            requests.Response: The response object containing the audio data.
        """
        speech_key = os.getenv("SPEECH_KEY")
        CHUNK_SIZE = 1024
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": speech_key
        }

        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        response = requests.post(url, json=data, headers=headers)
        return response
    
    def speak_instant(self, text):
        """
        Converts the given text to audio and plays it instantly.
        
        Args:
            text (str): The text to be converted to audio.
        """
        response = self.__get_response(text)
        audio_data = response.content
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        play(audio)
        return

    def save_to_file(self, filename, text,format="wav"):
        """
        Converts the given text to audio and saves it to a file.
        
        Args:
            filename (str): The name of the file to save the audio to.
            text (str): The text to be converted to audio.
        """
        response = self.__get_response(text)
        audio_data = response.content
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format)
        audio.export(filename, format=format)
        return

from transformers import VitsModel, VitsTokenizer
import torch
import numpy as np
class FacebookMMS(Speech):
    """
    FacebookMMS class for text-to-speech using Facebook MMS TTS model.
    """

    def __init__(self, language="en"):
        """
        Constructor for the FacebookMMS class.

        Args:
            language (str): The language to use for the model. Default is "en".
        """
        super().__init__()
        model_dir = os.path.join(MODELS_DIR,"facebook_mms_tts_eng")
        try:
            #try loading the model from the projects local src/models directory
            self.model = VitsModel.from_pretrained(model_dir)
            self.tokenizer = VitsTokenizer.from_pretrained(model_dir)
        except:
            self.model = VitsModel.from_pretrained("facebook/mms-tts-eng")
            self.tokenizer = VitsTokenizer.from_pretrained("facebook/mms-tts-eng")
    
    def __get_speech_data(self, text):
        """
        Generate speech data for the given text.

        Args:
            text (str): The input text to convert to speech.

        Returns:
            torch.Tensor: The speech data.
        """
        inputs = self.tokenizer(text, return_tensors="pt")
        input_ids = inputs["input_ids"]

        with torch.no_grad():
            outputs = self.model(input_ids)

        speech = outputs["waveform"]
        return speech
    
    def speak_instant(self, text):
        """
        Generate speech for the given text.

        Args:
            text (str): The input text to convert to speech.

        Returns:
            None
        """
        speech = self.__get_speech_data(text)

        # Convert the waveform to a NumPy array
        speech_np = speech.numpy()

        # Convert the waveform to an AudioSegment
        audio = AudioSegment(
            speech_np.tobytes(),
            frame_rate=16000,
            sample_width=speech_np.dtype.itemsize,
            channels=1
        )
        # Play the audio
        play(audio)
    
    def save_to_file(self, filename, text,format="wav"):
        """
        Generate speech for the given text and save it to a file.

        Args:
            filename (str): The name of the file to save the audio to.
            text (str): The input text to convert to speech.

        Returns:
            None
        """
        speech = self.__get_speech_data(text)

        # Convert the waveform to a NumPy array and scale it to 16-bit signed integers
        speech_np = (speech.numpy() * 32767).astype(np.int16)
        
        # Convert the waveform to an AudioSegment
        audio = AudioSegment(
            speech_np.tobytes(),
            frame_rate=16000,
            sample_width=2,  # 16-bit audio
            channels=1
        )
        # Save the audio to a file
        audio.export(filename, format=format)

if __name__ == "__main__":
    text="Hey! Long time no see. How's everything going with you? I just got back from a weekend trip, and it was so refreshing.  Did you catch the game last night? It was pretty intense!"

    speech1 = Pyttsx3Speech() 
    speech2 = ElevenLabsSpeech() 
    speech3 = FacebookMMS() 

    print("\n\n")
    start_time = time.time()
    speech1.speak_instant(text) #for the above text, took 12-13sec
    print("Pyttsx3Speech: "," %s seconds" % (time.time() - start_time))
    
    start_time = time.time()
    speech2.speak_instant(text) #for the above text, took 13-14sec
    print("ElevenLabsSpeech: "," %s seconds" % (time.time() - start_time))

    start_time = time.time()
    speech3.speak_instant(text) #for the above text, took 17-18sec
    print("FacebookMMS: ","%s seconds" % (time.time() - start_time))