#!/usr/bin/env bash

set -o errexit

# Install production requirements for deployment
pip3 install -r requirements-prod.txt

python3 manage.py collectstatic --noinput

python3 manage.py makemigrations

python3 manage.py migrate