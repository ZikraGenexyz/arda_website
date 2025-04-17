#!/bin/bash

# Build the static files for Django
pip install -r requirements.txt
python manage.py collectstatic --noinput

# Create a bin directory if it doesn't exist
mkdir -p .vercel/bin

# Download FFmpeg static builds for Linux
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -O ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
FFMPEG_DIR=$(find . -type d -name "ffmpeg-*-amd64-static" | head -n 1)

# Copy the binaries to the bin directory
cp "${FFMPEG_DIR}/ffmpeg" "${FFMPEG_DIR}/ffprobe" .vercel/bin/

# Create a .vercelignore file to avoid uploading large temporary files
echo "ffmpeg.tar.xz" >> .vercelignore
echo "ffmpeg-*-amd64-static/" >> .vercelignore

# Make the binaries executable
chmod +x .vercel/bin/ffmpeg .vercel/bin/ffprobe

# Verify the binaries
.vercel/bin/ffmpeg -version
.vercel/bin/ffprobe -version

echo "FFmpeg and FFprobe have been installed in .vercel/bin/"