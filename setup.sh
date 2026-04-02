#!/usr/bin/env bash
set -euo pipefail

echo "Installing Python packages from requirements.txt..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Downloading spaCy English model en_core_web_sm..."
python -m spacy download en_core_web_sm

echo "Setup complete."
