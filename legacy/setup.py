import os
import subprocess

# Step 0: Upgrade pip
print("Upgrading pip...")
subprocess.check_call(["pip3", "install", "--upgrade", "pip"])

# Step 1: Install dependencies
print("Installing dependencies...")
subprocess.check_call(["pip", "install", "-r", "requirements.txt"])

# Step 2: Run download_models.py
print("Downloading models...")
subprocess.check_call(["python", "download_models.py"])

# Step 3: Create necessary directories
print("Creating directories...")
os.makedirs("memory_stream/audio_logs", exist_ok=True)
os.makedirs("memory_stream/vision_logs", exist_ok=True)
os.makedirs("memory_stream/hearing_logs", exist_ok=True)
os.makedirs("memory_stream/people_logs", exist_ok=True)