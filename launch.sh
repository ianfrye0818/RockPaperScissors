#!/bin/bash

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    # Kill server if it exists
    if [ ! -z "$server_pid" ]; then
        kill $server_pid 2>/dev/null
    fi
    # Kill any processes using port 5555
    lsof -ti:5555 | xargs kill -9 2>/dev/null
    # Kill clients if they exist
    if [ ! -z "$client1_pid" ]; then
        kill $client1_pid 2>/dev/null
    fi
    if [ ! -z "$client2_pid" ]; then
        kill $client2_pid 2>/dev/null
    fi
    echo "Killed all processes"
    exit 0
}

# Set trap to cleanup on script exit or Ctrl+C
trap cleanup SIGINT SIGTERM EXIT

# Kill any existing processes on port 5555
echo "Checking for existing server on port 5555..."
lsof -ti:5555 | xargs kill -9 2>/dev/null && echo "Killed existing process on port 5555" || echo "Port 5555 is available"
sleep 1

# Start server
echo "Starting server..."
python3 Server/Server.py &
server_pid=$!

# Wait a moment for server to start
sleep 2

# Check if server is still running
if ! kill -0 $server_pid 2>/dev/null; then
    echo "ERROR: Server failed to start!"
    exit 1
fi

echo "Server is running (PID: $server_pid)"

# start client 1
echo "Starting client 1..."
python3 Client/RPSClient.py &
client1_pid=$!

# Wait a moment before starting client 2
sleep 1

# start client 2
echo "Starting client 2..."
python3 Client/RPSClient.py &
client2_pid=$!

echo "Done! All processes started."
echo "Press Ctrl+C to stop all processes"

# Wait for processes to finish - if ctrl+c is pressed, cleanup will handle it
wait
