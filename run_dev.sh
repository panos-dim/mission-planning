#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
REQUIRED_NODE_VERSION="$(cat "$ROOT_DIR/.nvmrc" 2>/dev/null || echo "22")"

BACKEND_PID=""
FRONTEND_PID=""
MONITOR_PID=""

echo "🚀 Starting development servers..."
echo ""

MONITOR_RESOURCES=false
MONITOR_INTERVAL=5

usage() {
    echo "Usage: ./run_dev.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --monitor              Enable CPU/Memory monitoring"
    echo "  --monitor-interval=N   Set monitoring interval in seconds (default: 5)"
    echo "  --help                 Show this help message"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --monitor)
            MONITOR_RESOURCES=true
            shift
            ;;
        --monitor-interval=*)
            MONITOR_INTERVAL="${1#*=}"
            MONITOR_RESOURCES=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo ""
            usage
            exit 1
            ;;
    esac
done

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "❌ Missing required command: $1"
        exit 1
    fi
}

resolve_python_bin() {
    if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
        printf '%s\n' "$ROOT_DIR/.venv/bin/python"
        return
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return
    fi
    echo "❌ Python 3 not found. Create .venv or install python3."
    exit 1
}

PYTHON_BIN="$(resolve_python_bin)"

export NVM_DIR="$HOME/.nvm"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    nvm use "$REQUIRED_NODE_VERSION" > /dev/null 2>&1 || \
        echo "⚠️  Node $REQUIRED_NODE_VERSION not found in nvm. Run: nvm install $REQUIRED_NODE_VERSION"
fi

require_cmd node
require_cmd npm
require_cmd curl
require_cmd lsof

mkdir -p "$RUN_DIR" "$ROOT_DIR/logs"

echo "Using Python $("$PYTHON_BIN" --version 2>&1)"
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

# Functions for tracked project processes and port checks
port_pids() {
    lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null || true
}

stop_tracked_process() {
    local pid_file=$1
    local label=$2
    if [[ ! -f "$pid_file" ]]; then
        return
    fi

    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    rm -f "$pid_file"

    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "🔧 Stopping previous tracked $label server ($pid)..."
        kill_tree "$pid"
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            force_kill_tree "$pid"
        fi
    fi
}

assert_port_free() {
    local port=$1
    local pids
    pids="$(port_pids "$port")"

    if [[ -z "$pids" ]]; then
        return
    fi

    echo "❌ Port $port is already in use by:"
    while IFS= read -r pid; do
        [[ -n "$pid" ]] || continue
        local command
        command="$(ps -p "$pid" -o command= 2>/dev/null || echo "unknown command")"
        echo "   PID $pid: $command"
    done <<< "$pids"

    echo ""
    echo "Refusing to kill unrelated local processes automatically."
    echo "Stop the process above and re-run, or clear stale PID files in $RUN_DIR if needed."
    exit 1
}

# Function to gracefully stop a process tree (SIGTERM first, then SIGKILL)
kill_tree() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "🔧 Sending SIGTERM to process $pid..."
        kill -TERM "$pid" 2>/dev/null
    fi
}

# Function to force kill a process tree
force_kill_tree() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        # Get all child PIDs
        local children
        children="$(pgrep -P "$pid" || true)"
        # Kill children first
        for child in $children; do
            force_kill_tree "$child"
        done
        # Kill the parent
        echo "🔧 Force killing process $pid..."
        kill -9 "$pid" 2>/dev/null
    fi
}

cleanup() {
    local exit_code=${1:-0}
    trap - EXIT SIGINT SIGTERM

    echo ""
    echo "🛑 Stopping servers gracefully..."

    # Stop resource monitor if running
    if [[ -n "${MONITOR_PID}" ]] && kill -0 "$MONITOR_PID" 2>/dev/null; then
        kill "$MONITOR_PID" 2>/dev/null || true
    fi

    # Send SIGTERM to allow graceful shutdown (process pool cleanup)
    kill_tree "$BACKEND_PID"
    kill_tree "$FRONTEND_PID"

    # Wait for graceful shutdown (allows Python to cleanup process pool)
    echo "⏳ Waiting for graceful shutdown (3s)..."
    sleep 3

    # Force kill any remaining processes
    if { [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; } || \
       { [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; }; then
        echo "⚠️  Force killing remaining processes..."
        force_kill_tree "$BACKEND_PID"
        force_kill_tree "$FRONTEND_PID"
    fi

    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"

    echo "✅ All servers stopped"
    exit "$exit_code"
}

trap 'cleanup $?' EXIT
trap 'cleanup 130' SIGINT SIGTERM

stop_tracked_process "$BACKEND_PID_FILE" "backend"
stop_tracked_process "$FRONTEND_PID_FILE" "frontend"

assert_port_free 8000
assert_port_free 3000

echo "Backend will start on: http://localhost:8000"
echo "Frontend will start on: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Start backend in background with hot reload
echo "Starting backend with hot reload..."
(
    cd "$ROOT_DIR"
    PYTHONPATH=. "$PYTHON_BIN" -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
) &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

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
(
    cd "$FRONTEND_DIR"
    npm run dev
) &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

# Start resource monitor if enabled
MONITOR_PID=""
if [ "$MONITOR_RESOURCES" = true ]; then
    echo ""
    monitor_resources &
    MONITOR_PID=$!
    echo ""
fi

# Wait for both processes
wait "$BACKEND_PID" "$FRONTEND_PID"
