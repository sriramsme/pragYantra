import os
from utils import verbose_print
# path to your models directory
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

#path to your memory stream directory, where all logs are saved
MEMORY_STREAM_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory_stream")
