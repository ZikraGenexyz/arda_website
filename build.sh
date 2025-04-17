# #!/bin/bash

# # Make the script exit on failures
# set -e

# # Install Python dependencies
# echo "Installing Python dependencies..."
# pip3 install -r requirements.txt

# # Create necessary directories
# echo "Setting up directories..."
# mkdir -p staticfiles/video
# mkdir -p staticfiles/image
# mkdir -p staticfiles/fonts

# # Ensure static files
# echo "Collecting static files..."
# if [ -d "public/video" ] && [ -f "public/video/liolio.mp4" ]; then
#   cp -r public/video/* staticfiles/video/
# fi

# if [ -d "public/image" ] && [ -f "public/image/frame.png" ]; then
#   cp -r public/image/* staticfiles/image/
# fi

# if [ -d "public/fonts" ]; then
#   cp -r public/fonts/* staticfiles/fonts/
# fi

# # Run Django collectstatic
# python3 manage.py collectstatic --noinput

# echo "Build completed successfully!"

#!/usr/bin/env bash

set -o errexit

pip3 install -r requirements.txt

python3 manage.py collectstatic --noinput

python3 manage.py makemigrations

python3 manage.py migrate