from datetime import datetime
import numpy as np
import librosa
import tensorflow as tf
# import tensorflow_hub as hub

# Load VGGish model (you should do this once, outside the function)
# vggish_model = hub.load('https://tfhub.dev/google/vggish/1')

def generate_vggish_embedding(audio_buffer, sample_rate=16000):
    """
    Generate VGGish embedding from an audio buffer.

    Parameters:
    audio_buffer (np.array): Audio data as a numpy array.
    sample_rate (int): Sample rate of the audio data. Default is 16000 Hz.

    Returns:
    np.array: VGGish embedding.
    """
    # Ensure audio is float32 and normalized
    audio = audio_buffer.astype(np.float32)
    audio = audio / np.max(np.abs(audio))

    # Resample if necessary
    if sample_rate != 16000:
        audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

    # Pad or trim to 1 second (16000 samples)
    if len(audio) < 16000:
        audio = np.pad(audio, (0, 16000 - len(audio)), 'constant')
    else:
        audio = audio[:16000]

    # Reshape audio to match VGGish input shape
    audio = np.reshape(audio, (1, -1))

    # Convert to TensorFlow tensor
    audio_tensor = tf.convert_to_tensor(audio, dtype=tf.float32)

    # Generate embeddings
    embeddings = vggish_model(audio_tensor)
    
    # Average pooling over time frames
    embedding = np.mean(embeddings.numpy(), axis=0)

    return embedding


class LiveMemory:
    """
    LiveMemory class retrieve data from memory logs.

    """
    def __init__(self, vision_buffer, audio_buffer,latest_time_threshold=5):
        """
        Initializes a Memory object.

        Args:
            latest_time_threshold (int, optional): The time threshold (in seconds) for considering a memory entry as the latest. Defaults to 5 seconds.
        """
        self.latest_time_threshold = latest_time_threshold
        self.vision_buffer = vision_buffer
        self.audio_buffer = audio_buffer

    @staticmethod
    def get_recent_context(deque_lis,min_threshold=0,max_threshold=10):
        """
        Get the recent context from the deque.

        Parameters:
        relevance_threshold (int): The relevance threshold in seconds. Default is None.
        """
        now = datetime.now()
        x = [
            text for timestamp, text in deque_lis
            if min_threshold <= (now - timestamp).total_seconds() <= max_threshold
        ]
        return " ".join(x)
    


if __name__ == "__main__":
    memory = LiveMemory(latest_time_threshold=600)
    print(memory.get_latest_memory())