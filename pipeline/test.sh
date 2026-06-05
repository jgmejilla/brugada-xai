#!/bin/bash

# Test script to identify and process ECG files

BASE_DIR="/home/elijah/CS19X-Brugada-Syndrome-Classifier/results/3-2-2026"

# Start ollama serve in background if not already running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama server..."
    ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3  # Wait for server to start
else
    echo "Ollama server already running"
fi

echo ""
echo "Looking for all .txt files in results/3-2-2026..."
echo ""

# List all txt files
FILES=$(ls -1 /home/elijah/CS19X-Brugada-Syndrome-Classifier/results/3-2-2026/*tive*.txt 2>/dev/null)

if [ -z "$FILES" ]; then
    echo "No .txt files found!"
    exit 1
fi

echo "Found the following files:"
echo "$FILES" | nl

echo ""
echo "File count:"
echo "$FILES" | wc -l

# Load prompt from !prompt.txt
PROMPT_FILE="/home/elijah/CS19X-Brugada-Syndrome-Classifier/results/3-2-2026/!prompt.txt"
if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: !prompt.txt not found!"
    exit 1
fi

PROMPT=$(cat "$PROMPT_FILE")

echo ""
echo "=== Processing First 5 Files Through Ollama ==="
echo ""

# Get first 5 files and display their contents
echo "$FILES" | while IFS= read -r file; do
    filename=$(basename "$file")
    
    # Extract label from filename
    if [[ "$filename" == *"negative"* ]]; then
        TRUE_LABEL="negative"
    else
        TRUE_LABEL="positive"
    fi
    
    # Read ECG narration
    DESCRIPTION=$(cat "$file")
    
    # Combine prompt template with narration
    FULL_PROMPT="${PROMPT}${DESCRIPTION}"
    
    echo "--- $filename (True: $TRUE_LABEL) ---"
    # echo $FULL_PROMPT
    
    # Send to Ollama (reuses running server - much faster)
    RESPONSE=$(echo "$FULL_PROMPT" | timeout 60 ollama run qwen3:latest 2>&1)
    echo "$RESPONSE"
done

echo "Done"
