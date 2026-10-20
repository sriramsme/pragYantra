#!/bin/bash

# Step 0: Upgrade pip
echo "Upgrading pip..."
pip3 install --upgrade pip

sudo apt install build-essential portaudio19-dev

# Step 1: Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Step 2: Run download_models.py
echo "Downloading models..."
python3 download_models.py

# Step 3: Create necessary directories
echo "Creating directories..."
mkdir -p memory_stream/vision_logs
mkdir -p memory_stream/hearing_logs
mkdir -p memory_stream/people_logs
mkdir -p memory_stream/audio_logs

echo "Setup completed successfully."