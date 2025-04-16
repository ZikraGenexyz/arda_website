#!/bin/bash

# Make the script exit on failures
set -e

# Install system dependencies
echo "Installing system dependencies..."
apt-get update -y
apt-get install -y --no-install-recommends ffmpeg

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Setting up directories..."
mkdir -p staticfiles/video
mkdir -p staticfiles/image
mkdir -p staticfiles/fonts

# Ensure static files
echo "Collecting static files..."
if [ -d "public/video" ] && [ -f "public/video/liolio.mp4" ]; then
  cp -r public/video/* staticfiles/video/
fi

if [ -d "public/image" ] && [ -f "public/image/frame.png" ]; then
  cp -r public/image/* staticfiles/image/
fi

if [ -d "public/fonts" ]; then
  cp -r public/fonts/* staticfiles/fonts/
fi

# Run Django collectstatic
python manage.py collectstatic --noinput

echo "Build completed successfully!"