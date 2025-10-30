#!/bin/bash
# Stop the Mixed TTS Server

echo "🛑 Stopping Mixed TTS Server..."

pkill -f "python backend/main.py"

if [ $? -eq 0 ]; then
    echo "✓ Server stopped successfully"
else
    echo "⚠️  No server was running"
fi
