#!/usr/bin/env bash

set -o errexit

# Determine if we're on Vercel
if [ -n "${VERCEL}" ]; then
  echo "Running on Vercel. Using minimal dependencies."
  # Use minimal requirements for Vercel
  pip3 install --no-cache-dir -r requirements-vercel.txt
else
  echo "Running locally or on another platform. Using full dependencies."
  # Use full requirements for local/other environments
  pip3 install --no-cache-dir -r requirements.txt
fi

# Install SQLite alternative for Vercel (specify --no-deps to avoid dependency conflicts)
pip3 install --no-cache-dir pysqlite3-binary==0.5.4 --no-deps

# Optimize packages: try to find and remove unnecessary files if possible
if [ -n "$VIRTUAL_ENV" ]; then
  echo "Cleaning up virtual environment at $VIRTUAL_ENV"
  find $VIRTUAL_ENV -name "tests" -type d -exec rm -rf {} \; 2>/dev/null || true
  find $VIRTUAL_ENV -name "examples" -type d -exec rm -rf {} \; 2>/dev/null || true
  find $VIRTUAL_ENV -name "docs" -type d -exec rm -rf {} \; 2>/dev/null || true
else
  echo "VIRTUAL_ENV not defined, skipping cleanup"
fi

# Clear pip cache
pip3 cache purge || true

# Collect static files
python3 manage.py collectstatic --noinput --clear

# Run migrations if needed
python3 manage.py makemigrations
python3 manage.py migrate