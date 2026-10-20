from time import sleep
import os
import threading
from llama_cpp import Llama as LlamaCPP
from core.hear import LiveTranscriber
from core.vision import LiveVision
from core.speech import LiveSpeech
from memory.memory import LiveMemory
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from . import MODELS_DIR, ENV_PATH, verbose_print


load_dotenv(ENV_PATH)

class Interpreter:
    """
    Interpreter class
    """
    def __init__(self,model_name):
        """
        Constructor
        """
        pass
    
    def get_response(self, prompt):
        """
        Get response from the interpreter.

        Args:
            prompt (str): The input prompt to generate a response for.

        Returns:
            str: The generated response from the model.
        """
        return NotImplementedError("Subclass must implement get_response method")
    
class Llama(Interpreter):
    """
    Llama class is an offline interpreter. It can be slow depending on the model size and device specs.
    It inherits from the Interpreter base class and provides an implementation for the get_response method.
    """
    def __init__(self,model_name="llama3_8B"):
        """
        Constructor for the Llama class.

        Args:
            model_name (str): Model filename. Defaults to "llama3_8B".
        """
        model_path=os.path.join(MODELS_DIR,model_name+".gguf")
        if os.path.exists(model_path):
            self._llama = LlamaCPP(model_path=model_path)
        else:
            raise FileNotFoundError(f"Model file {model_path} not found.")
    
    def get_response(self, prompt):
        """
        Get response from the llama model.

        Args:
            prompt (str): The input prompt to generate a response for.

        Returns:
            str: The generated response from the model.
        """
        #max_tokens: The maximum number of tokens to generate. Shorter token lengths will provide faster performance.

        #temperature: The temperature of the sampling distribution. Lower temperatures will result in more deterministic outputs, 
        #while higher temperatures will result in more random outputs.

        #top_p: An alternative to sampling with temperature, where the model considers the results of the tokens with top_p probability mass. 
        #       Lower values of top_p will result in more deterministic outputs, while higher values will result in more random outputs.

        #echo: Whether to echo the prompt in the output.

        # Define the parameters
        model_output = self._llama(
            prompt,
            max_tokens=200,
            temperature=0.3,
            top_p=0.1,
            echo=False,
        )
        final_result = model_output["choices"][0]["text"].strip()

        return final_result
    
class Groq(Interpreter):
    """
    Groq class. Online and super fast.

    This class represents a Groq interpreter that can be used to interact with the Groq API.
    It provides methods to initialize the interpreter and get responses from the Groq API.

    Attributes:
        model_name (str): The name of the Groq model to use.
        groq_api_key (str): The API key for accessing the Groq API.
        temperature (float): The temperature parameter for generating responses. Default is 0.

    Methods:
        __init__(model_name, groq_api_key, temperature=0): Initializes the Groq interpreter.
        get_response(prompt): Sends a prompt to the Groq API and returns the response.

    """
    def __init__(self, model_name, groq_api_key=None, temperature=0):
        """
        Constructor

        Args:
            model_name (str): The name of the Groq model to use.
            groq_api_key (str): The API key for accessing the Groq API. If not provided, it will be read from the environment variable GROQ_API_KEY.
            temperature (float, optional): The temperature parameter for generating responses. Default is 0.
        """
        if groq_api_key is None:
            groq_api_key = os.getenv("GROQ_API_KEY")
        try:
            self._groq = ChatGroq(temperature=temperature, model_name=model_name, groq_api_key=groq_api_key)
            self.get_response("Checking if the model is initialized correctly.")
        except Exception as e:
            print("Make sure the model name is correct and you have the Groq API key.\nCheck the supported models here: https://console.groq.com/docs/models")
            raise e
    
    def get_response(self, prompt):
        """
        Get response from the groq

        Args:
            prompt (str): The prompt to send to the Groq API.

        Returns:
            str: The response from the Groq API.
        """
        prompt = ChatPromptTemplate.from_messages([("system", prompt)])

        chain = prompt | self._groq
        model_output2=  chain.invoke({})
        final_result= model_output2.content
        return final_result
    
# central processing unit for all the data coming from the sources
class Manas:
    """
    Manas class represents a virtual brain that can process multiple inputs from different sources like eyes and ears.
    It can see, hear, speak, and understand the world around it.
    """

    def __init__(self,interpreter_model,offline_mode=True,groq_api_key=None,speaker_model="pyttsx3",no_vision=False):
        """
        Constructor

        Args:
            offline_mode (bool): Whether to run in offline mode. Default is False.
            interpreter_model (str): The name of the model to use.

        IF running in offline mode, the Llama model will be used for interpretation. 
        Make sure you have the model file in the models directory.
        """
        if not offline_mode:
            # Running in online mode. Make sure the model name is correct and you have the Groq API key.
            self.interpreter = Groq(model_name=interpreter_model, groq_api_key=groq_api_key)
        else:
            #Running in offline mode.\nMake sure you have the quantized GGUF model file in the models directory
            self.interpreter = Llama(model_name=interpreter_model)
        
        self.ears = LiveTranscriber()
        if no_vision:
            self.eyes = None
            vision_buffer=None
        else:
            self.eyes = LiveVision()
            vision_buffer=self.eyes._aid.memory_buffer
        self.speak = LiveSpeech(transcriber=self.ears,speaker_model=speaker_model)
        self.memory = LiveMemory(vision_buffer=vision_buffer,
                                 audio_buffer=self.ears._aid.memory_buffer,
                                 latest_time_threshold=7)
        self.alive = False
        self.live_thread = None

        return

    def setup(self):
        """
        Setup all the core sense components
        """
        self.ears.start()

        if self.eyes is not None:
            self.eyes.start()
        self.speak.start()
        self.alive = True
        return

    def start(self):
        """
        Start the Manas
        """
        self.live_thread = threading.Thread(target=self.live)
        self.live_thread.start()
        return
    def terminate(self):
        """
        End the Manas
        """
        if self.live_thread is not None:
            self.alive = False
            self.live_thread.join(timeout=3.0)  # Wait for the live thread to finish

        self.ears.terminate()
        if self.eyes is not None:
            self.eyes.terminate()
        self.speak.terminate()

        print("All terminated.")
        return

    def analyze(self,previous_response):
        """
        Analyze the data

        Args:
            previous_response (str): The previous response
        Returns:
            str: The conversational response generated by the Manas.
        """
        recent_audio, latest_audio = self.ears.get_previous_current_transcription()

        if self.eyes is not None:
            recent_vision, latest_vision = self.eyes.get_previous_current_context()
            vision_prompt = f"""
            What you saw recently: {recent_vision}
            What you see currently: {latest_vision}
            """
        else:
            vision_prompt = "Vision is not available."

        verbose_print(latest_audio)
  
        prompt = f"""
        You are like a virtual brain of a human processing multiple inputs from different sources like ears, and possibly eyes. You can hear, speak, and understand the world around you. If vision is available, you can also see.

        Here is what you heard recently (about 2-3 seconds ago):
        {recent_audio}

        Your previous response was: "{previous_response}"

        Here is your current sensory input:

        {vision_prompt}

        What you hear currently: {latest_audio}

        Using this current information, generate a conversational response as if you are a human, talking. If vision is not available, base your response solely on the audio input.
        """

        response = self.interpreter.get_response(prompt)

        return response

    def live(self):
        """
        Bring it to life
        """
        response = ""
        
        self.speak.speak("Hello there. How is it going?")
        while self.speak.is_speaking():
            sleep(0.1)

        while self.alive:
            # If the AI is currently speaking, make sure transcription is paused
            if not self.speak.is_speaking() and self.ears._aid.is_ready_for_processing():
                        
                # Process the new transcription
                response = self.analyze(previous_response=response)
                
                # Speak the response
                self.speak.speak(response)
                
                # Wait until speaking is finished
                while self.speak.is_speaking():
                    sleep(0.1)
                
                # Force complete the current phrase after speaking
                self.ears._aid.force_complete_phrase()
                
            
            # Small delay to prevent tight looping
            sleep(0.1)
        
if __name__ == '__main__':
    manas = Manas()
    # manas.start()

    data = {"vision":"A man working looking at his phone",
            "audio" :"It is a beautiful day outside today."}
    response = manas.analyze(data)

    print(response)