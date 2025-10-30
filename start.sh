#!/bin/bash
# Mixed TTS Startup Script

echo "🎙️  Starting Mixed Language TTS Server..."
echo ""

# Navigate to project directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Check if server is already running
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Server already running on port 5000"
    echo "To stop it: pkill -f 'python backend/main.py'"
    echo ""
else
    # Start the backend server
    echo "✓ Activating virtual environment..."
    echo "✓ Starting Flask backend on http://127.0.0.1:5000..."
    python backend/main.py &
    SERVER_PID=$!
    
    # Wait for server to start
    sleep 3
    
    # Check if server started successfully
    if curl -s http://127.0.0.1:5000/health > /dev/null 2>&1; then
        echo "✓ Backend server is running (PID: $SERVER_PID)"
        echo ""
        echo "🌐 Opening frontend in browser..."
        xdg-open frontend/index.html
        echo ""
        echo "========================================="
        echo "Mixed TTS is ready!"
        echo "Backend: http://127.0.0.1:5000"
        echo "Frontend: Check your browser"
        echo "========================================="
        echo ""
        echo "Press Ctrl+C to stop the server"
        echo ""
        
        # Keep script running to show server logs
        wait $SERVER_PID
    else
        echo "❌ Failed to start server"
        exit 1
    fi
fi
