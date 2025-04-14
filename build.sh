#!/usr/bin/env bash

set -o errexit

# Install all dependencies
pip3 install -r requirements.txt

# Install SQLite alternative for Vercel
pip3 install pysqlite3-binary

# Collect static files
python3 manage.py collectstatic --noinput

# Uncomment if you need to run migrations during build
# python manage.py makemigrations
# python manage.py migrate