#!/bin/bash
set -e

echo "=== Changing to app directory ==="
cd /home/site/wwwroot/summarizer-app

echo "=== Installing Python dependencies ==="
if [ -f requirements.txt ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "No requirements.txt found, skipping pip install."
fi

echo "=== Starting the app ==="
python run.py
