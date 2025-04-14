#!/usr/bin/env bash

set -o errexit

# Install dependencies
pip3 install -r requirements.txt

# Collect static files
python3 manage.py collectstatic --noinput

# Create fake database settings for collectstatic and migrations
# This environment variable will be used instead of SQLite
export DATABASE_URL="postgresql://fake:fake@fake:5432/fake"

# Run migrations with fake database URL
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput

echo "Build completed successfully"