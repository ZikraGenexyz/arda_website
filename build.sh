#!/usr/bin/env bash

set -o errexit

pip3 install -r requirements.txt

python3 manage.py collectstatic --noinput

python3 manage.py makemigrations

python3 manage.py migrate