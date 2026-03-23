#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
PYTEST_BIN="${PYTHON_BIN%/python}/pytest"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_HOST="${RELEASE_GATE_HOST:-127.0.0.1}"
BACKEND_PORT="${RELEASE_GATE_PORT:-}"
SERVER_LOG="$(mktemp -t mission-planning-release-gate.XXXXXX.log)"
SERVER_PID=""
TEST_BASE_URL=""

log() {
  printf '[release-gate] %s\n' "$*"
}

die() {
  printf '[release-gate] ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill -INT "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  rm -f "${SERVER_LOG}"
}

trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

assert_file() {
  [[ -f "$1" ]] || die "Missing required file: $1"
}

port_is_in_use() {
  python3 - <<'PY' "${BACKEND_HOST}" "${BACKEND_PORT}"
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(0.5)
try:
    sys.exit(0 if sock.connect_ex((host, port)) == 0 else 1)
finally:
    sock.close()
PY
}

pick_free_port() {
  python3 - <<'PY' "${BACKEND_HOST}"
import socket
import sys

host = sys.argv[1]
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((host, 0))
port = sock.getsockname()[1]
sock.close()
print(port)
PY
}

wait_for_http() {
  local path="$1"
  local attempts="${2:-40}"
  local url="http://${BACKEND_HOST}:${BACKEND_PORT}${path}"

  for _ in $(seq 1 "${attempts}"); do
    if curl -sf "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done

  log "Server log tail:"
  tail -n 40 "${SERVER_LOG}" || true
  die "Timed out waiting for ${url}"
}

print_route_latency_summary() {
  local payload
  payload="$(curl -sf "http://${BACKEND_HOST}:${BACKEND_PORT}/api/v1/dev/route-latency?limit=20")"
  python3 - <<'PY' "${payload}"
import json
import sys

payload = json.loads(sys.argv[1])
status_counts = payload.get("status_counts", {})
families = payload.get("families", [])
hot_count = sum(int(f.get("hot_count", 0)) for f in families)
five_xx = int(status_counts.get("5xx", 0))

print(
    "[release-gate] Observability: "
    f"2xx={status_counts.get('2xx', 0)} "
    f"4xx={status_counts.get('4xx', 0)} "
    f"5xx={five_xx} "
    f"hot_families={hot_count}"
)

if five_xx:
    raise SystemExit("release gate failed: observed 5xx responses in route-latency snapshot")
PY
}

main() {
  require_cmd curl
  require_cmd npm
  require_cmd python3
  assert_file "${PYTHON_BIN}"
  assert_file "${PYTEST_BIN}"
  [[ -d "${FRONTEND_DIR}" ]] || die "Missing frontend directory"

  if [[ -z "${BACKEND_PORT}" ]]; then
    BACKEND_PORT="$(pick_free_port)"
  elif port_is_in_use; then
    die "Port ${BACKEND_PORT} is already in use on ${BACKEND_HOST}. Stop the existing server or choose a different RELEASE_GATE_PORT."
  fi

  TEST_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"

  log "Starting backend server on ${BACKEND_HOST}:${BACKEND_PORT}"
  (
    cd "${ROOT_DIR}"
    PYTHONPATH=. "${PYTHON_BIN}" -m uvicorn backend.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}"
  ) >"${SERVER_LOG}" 2>&1 &
  SERVER_PID="$!"

  wait_for_http "/health"
  wait_for_http "/ready"

  log "Running backend test suite against ${TEST_BASE_URL}"
  (
    cd "${ROOT_DIR}"
    MISSION_PLANNER_TEST_BASE_URL="${TEST_BASE_URL}" \
      PYTHONPATH=. "${PYTEST_BIN}" tests/unit tests/integration tests/e2e -o addopts='' -n 0 -q
  )

  log "Running frontend tests"
  (
    cd "${FRONTEND_DIR}"
    npm run test:run -- --reporter=dot
  )

  log "Building frontend"
  (
    cd "${FRONTEND_DIR}"
    npm run build
  )

  log "Checking health and readiness"
  curl -sf "http://${BACKEND_HOST}:${BACKEND_PORT}/health" >/dev/null
  curl -sf "http://${BACKEND_HOST}:${BACKEND_PORT}/ready" >/dev/null

  log "Inspecting route latency snapshot"
  print_route_latency_summary

  log "Release gate passed"
}

main "$@"
