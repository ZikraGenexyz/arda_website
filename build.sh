#!/usr/bin/env bash

set -o errexit

# Install dependencies
pip3 install -r requirements.txt

# Collect static files
python3 manage.py collectstatic --noinput

# Make and apply migrations
python3 manage.py makemigrations
python3 manage.py migrate