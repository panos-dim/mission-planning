#!/bin/bash
echo "🚀 Starting development servers..."
echo ""

# Parse command line arguments
MONITOR_RESOURCES=false
MONITOR_INTERVAL=5
for arg in "$@"; do
    case $arg in
        --monitor)
            MONITOR_RESOURCES=true
            shift
            ;;
        --monitor-interval=*)
            MONITOR_INTERVAL="${arg#*=}"
            MONITOR_RESOURCES=true
            shift
            ;;
        --help)
            echo "Usage: ./run_dev.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --monitor              Enable CPU/Memory monitoring"
            echo "  --monitor-interval=N   Set monitoring interval in seconds (default: 5)"
            echo "  --help                 Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# Load nvm and use Node 22 (required for Vite 7)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 22 > /dev/null 2>&1 || echo "⚠️  Node 22 not found. Run: nvm install 22"

echo "Using Node.js $(node --version)"
echo ""

# Resource monitoring function
monitor_resources() {
    local log_file="logs/resource_monitor.log"
    mkdir -p logs

    echo "📊 Resource Monitor Started (interval: ${MONITOR_INTERVAL}s)" | tee "$log_file"
    echo "   Log file: $log_file"
    echo "-------------------------------------------" >> "$log_file"

    while true; do
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

        # Get system-wide CPU and memory
        local cpu_usage=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | tr -d '%')
        local mem_pressure=$(memory_pressure 2>/dev/null | grep "System-wide memory free percentage" | awk '{print $5}' || echo "N/A")

        # Get process-specific stats for our servers
        local backend_stats=$(ps -p $BACKEND_PID -o %cpu,%mem,rss 2>/dev/null | tail -1 || echo "- - -")
        local frontend_stats=$(ps -p $FRONTEND_PID -o %cpu,%mem,rss 2>/dev/null | tail -1 || echo "- - -")

        # Get node processes (Vite dev server spawns child processes)
        local node_cpu=$(ps aux | grep -E "node|vite" | grep -v grep | awk '{sum += $3} END {print sum}')
        local node_mem=$(ps aux | grep -E "node|vite" | grep -v grep | awk '{sum += $4} END {print sum}')

        # Get Python processes
        local python_cpu=$(ps aux | grep -E "python|uvicorn" | grep -v grep | awk '{sum += $3} END {print sum}')
        local python_mem=$(ps aux | grep -E "python|uvicorn" | grep -v grep | awk '{sum += $4} END {print sum}')

        # Log to file
        echo "[$timestamp]" >> "$log_file"
        echo "  System CPU: ${cpu_usage:-N/A}% | Free Mem: ${mem_pressure:-N/A}" >> "$log_file"
        echo "  Node (Vite): CPU ${node_cpu:-0}% | Mem ${node_mem:-0}%" >> "$log_file"
        echo "  Python (Backend): CPU ${python_cpu:-0}% | Mem ${python_mem:-0}%" >> "$log_file"
        echo "" >> "$log_file"

        # Print condensed version to console
        printf "\r📊 [%s] Node: %.1f%% CPU | Python: %.1f%% CPU | System: %s%% CPU    " \
            "$(date '+%H:%M:%S')" "${node_cpu:-0}" "${python_cpu:-0}" "${cpu_usage:-N/A}"

        sleep $MONITOR_INTERVAL
    done
}

# Function to kill process using a specific port
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port)
    if [ -n "$pids" ]; then
        echo "🔧 Killing process(es) on port $port..."
        echo "$pids" | xargs kill -9 2>/dev/null
        sleep 1
    fi
}

# Function to gracefully stop a process tree (SIGTERM first, then SIGKILL)
kill_tree() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        echo "🔧 Sending SIGTERM to process $pid..."
        kill -TERM $pid 2>/dev/null
    fi
}

# Function to force kill a process tree
force_kill_tree() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        # Get all child PIDs
        local children=$(pgrep -P $pid)
        # Kill children first
        for child in $children; do
            force_kill_tree $child
        done
        # Kill the parent
        echo "🔧 Force killing process $pid..."
        kill -9 $pid 2>/dev/null
    fi
}

# Kill any processes using our ports
kill_port 8000
kill_port 3000

echo "Backend will start on: http://localhost:8000"
echo "Frontend will start on: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Stopping servers gracefully..."

    # Stop resource monitor if running
    if [ -n "$MONITOR_PID" ] && kill -0 $MONITOR_PID 2>/dev/null; then
        kill $MONITOR_PID 2>/dev/null
    fi

    # Send SIGTERM to allow graceful shutdown (process pool cleanup)
    kill_tree $BACKEND_PID
    kill_tree $FRONTEND_PID

    # Wait for graceful shutdown (allows Python to cleanup process pool)
    echo "⏳ Waiting for graceful shutdown (3s)..."
    sleep 3

    # Force kill any remaining processes
    if kill -0 $BACKEND_PID 2>/dev/null || kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "⚠️  Force killing remaining processes..."
        force_kill_tree $BACKEND_PID
        force_kill_tree $FRONTEND_PID
    fi

    # Also kill any remaining processes on our ports as a safety measure
    sleep 1
    kill_port 8000
    kill_port 3000

    echo "✅ All servers stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Start backend in background with hot reload
echo "Starting backend with hot reload..."
pdm run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to become healthy, then auto-generate API types
echo "Waiting for backend to start..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:8000/openapi.json > /dev/null 2>&1; then
        echo "✅ Backend is up"
        echo "🔄 Auto-generating API types..."
        (cd frontend && npm run generate:api-types 2>/dev/null) && echo "✅ API types generated" || echo "⚠️  API type generation failed (non-blocking)"
        break
    fi
    sleep 1
done

# Start frontend in background
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Start resource monitor if enabled
MONITOR_PID=""
if [ "$MONITOR_RESOURCES" = true ]; then
    echo ""
    monitor_resources &
    MONITOR_PID=$!
    echo ""
fi

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
