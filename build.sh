#!/usr/bin/env bash

set -o errexit

# Install production requirements for deployment
pip3 install -r requirements.txt

python3 manage.py collectstatic --noinput

python3 manage.py makemigrations

python3 manage.py migrate