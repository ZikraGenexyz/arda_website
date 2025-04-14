#!/bin/bash

echo "Starting Vercel build process with minimal dependencies..."

# Install only what's needed for serving the web app
pip install --no-cache-dir -r requirements-vercel.txt

# Install SQLite alternative
pip install --no-cache-dir pysqlite3-binary==0.5.4 --no-deps

# Clean up any temporary files
rm -rf /tmp/*

# Collect static files
python manage.py collectstatic --noinput --clear

# Run migrations (for database structure only)
python manage.py makemigrations
python manage.py migrate

echo "Vercel build process completed" 