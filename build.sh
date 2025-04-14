#!/usr/bin/env bash

set -o errexit

# Install all dependencies
pip3 install -r requirements.txt

# Install SQLite alternative for Vercel (specify --no-deps to avoid dependency conflicts)
pip3 install pysqlite3-binary==0.5.4 --no-deps

# Collect static files
python3 manage.py collectstatic --noinput

# Uncomment if you need to run migrations during build
python3 manage.py makemigrations
python3 manage.py migrate