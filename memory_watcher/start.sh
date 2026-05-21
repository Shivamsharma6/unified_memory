#!/bin/bash
cd "$(dirname "$0")"

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install requirements
source venv/bin/activate
pip install -r requirements.txt

# Run the watcher
echo "Starting Memory Watcher..."
python main.py
