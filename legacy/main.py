import argparse
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()
import logging
from transformers import logging as hf_logging
logging.basicConfig(level=logging.ERROR)
hf_logging.set_verbosity_error()
from config import Config

def main():
    parser = argparse.ArgumentParser(description='pragYantra')
    parser.add_argument('--offline_mode', action='store_true', help='Whether to run in offline mode. Run the assistant without making network requests. Uses local resources instead.\nDefault is True.')
    parser.add_argument('--interpreter_model', type=str, default='llama3-70B-8192', help='The name of the model to use. For online mode, check models aavailable on https://console.groq.com/docs/models. For offline mode, make sure you have quantized gguf file like llama3_8B.gguf in models folder.')
    parser.add_argument('--speaker_model', type=str, default='pyttsx3', help='The speaker model to use. Available options are pyttsx3, facebook-mms and 11labs(requires online connection).\nDefault is pyttsx3.')
    parser.add_argument('--no_vision', action='store_true',default=False, help='Whether to enable vision input or not.\nDefault is False.')
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    if not args.offline_mode:
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key is None:
            raise EnvironmentError("Please set the GROQ_API_KEY environment variable to use online mode.")
    else:
        model_path = os.path.join("models", args.interpreter_model+".gguf")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}. Please check the model name.\n\nRefer to this https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#pulling-models-from-hugging-face-hub for more details on how to get such model file.")
            
        
    if args.speaker_model not in ["pyttsx3", "11labs", "facebook-mms"]:
        raise ValueError("Invalid speaker model. Please choose from 'pyttsx3', '11labs', or 'facebook-mms'.")
        
    if args.speaker_model == "11labs":
        speech_key = os.getenv('SPEECH_KEY')
        if speech_key is None:
            raise EnvironmentError("Please set the SPEECH_KEY environment variable in a '.env' file to use Eleven Labs for speech model.")
    Config.set_verbose(args.verbose)
    print("\nHello! \nSetting up the pragYantra virtual assistant for you...\n")
    from core.manas import Manas
    robo = Manas(interpreter_model=args.interpreter_model, offline_mode=args.offline_mode, 
                 speaker_model=args.speaker_model,no_vision=args.no_vision)

    robo.setup()
    robo.start()

    # keep the program running
    try:
        print("\nSetup complete. You can interact with it now. There might be a slight delay before it can respond initially. \nPress Ctrl+C to terminate.\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTerminating...\n")
    finally:
        # Ensure termination happens even if an exception occurs
        robo.terminate()
        print("\nSee ya..Bye!")
        sys.exit(0)  # Ensure a clean exit

if __name__ == "__main__":
    main()