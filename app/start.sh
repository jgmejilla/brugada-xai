#!/bin/bash
# Startup script for ECG processing pipeline

echo "=== Brugada Syndrome Classifier - ECG Processing Pipeline ==="
echo ""

# Check if we're in the app directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this script from the app directory"
    exit 1
fi

# Install/Update backend dependencies
echo "Setting up Python backend..."
pip install -q -r requirements-backend.txt

# Start Flask backend in background
echo "Starting Flask backend on port 5000..."
python backend.py &
FLASK_PID=$!

# Give Flask time to start
sleep 2

# Start Svelte dev server
echo "Starting Svelte dev server on port 5173..."
npm run dev

# Cleanup
kill $FLASK_PID 2>/dev/null
