#!/usr/bin/env bash
# ==============================================================================
# Setup, start, and seed Google Cloud Firestore Emulator for Cymbal Retail Agent
# ==============================================================================
# Usage:
#   source ./scripts/setup-emulator.sh               # Starts, exports env, & seeds
#   ./scripts/setup-emulator.sh                      # Runs as subshell and seeds
#   ./scripts/setup-emulator.sh --port 8888          # Custom port
#   ./scripts/setup-emulator.sh --base-date 2026-08-18 # Specific reference date
# ==============================================================================

set -e

# Default settings
DEFAULT_PORT="8888"
DEFAULT_HOST="127.0.0.1"
HOST="${DEFAULT_HOST}"
PORT="${DEFAULT_PORT}"
BASE_DATE=""

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --host-port)
      HOST_PORT_ARG="$2"
      HOST="${HOST_PORT_ARG%%:*}"
      PORT="${HOST_PORT_ARG##*:}"
      shift 2
      ;;
    --base-date)
      BASE_DATE="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: [source] $0 [--host HOST] [--port PORT] [--host-port HOST:PORT] [--base-date YYYY-MM-DD]"
      echo ""
      echo "Options:"
      echo "  --host HOST         Host IP (default: 127.0.0.1)"
      echo "  --port PORT         Port number (default: 8888)"
      echo "  --host-port H:P     Combined host:port (default: 127.0.0.1:8888)"
      echo "  --base-date DATE    Reference date for order seeding (default: today)"
      echo "  -h, --help          Show this help message"
      return 0 2>/dev/null || exit 0
      ;;
    *)
      echo "Unknown option: $1"
      return 1 2>/dev/null || exit 1
      ;;
  esac
done

EMULATOR_TARGET="${HOST}:${PORT}"
EMULATOR_URL="http://${EMULATOR_TARGET}"

echo "============================================================"
echo " Firestore Emulator Setup & Idempotent Seeder"
echo " Target: ${EMULATOR_TARGET}"
echo "============================================================"

# 1. Verify Java Runtime (required by Firestore emulator)
if ! command -v java >/dev/null 2>&1; then
  echo "[-] ERROR: Java (JRE/JDK) is required to run the Firestore emulator but was not found."
  echo "    Please install Java: sudo apt-get install default-jre"
  return 1 2>/dev/null || exit 1
fi

# 2. Check if Firestore emulator component is installed
echo "[1/4] Checking Firestore emulator installation..."
if ! gcloud emulators firestore --help >/dev/null 2>&1; then
  echo "      Firestore emulator component is missing. Installing..."
  if gcloud components install cloud-firestore-emulator --quiet 2>/dev/null; then
    echo "      Successfully installed cloud-firestore-emulator."
  else
    echo "[-] WARNING: 'gcloud components install' failed (package manager managed)."
    echo "    Attempting to continue or install via package manager if needed:"
    echo "    sudo apt-get install google-cloud-cli-firestore-emulator"
  fi
else
  echo "      Firestore emulator component is installed."
fi

# 3. Check if emulator is already running on target host:port
echo "[2/4] Checking if emulator is running at ${EMULATOR_TARGET}..."
IS_RUNNING=false
if curl -s --connect-timeout 2 "${EMULATOR_URL}/" >/dev/null 2>&1; then
  IS_RUNNING=true
  echo "      Emulator is already running and responding at ${EMULATOR_TARGET}."
fi

if [ "$IS_RUNNING" = false ]; then
  echo "      Starting Firestore emulator in the background..."
  LOG_FILE="/tmp/firestore-emulator-${PORT}.log"
  gcloud emulators firestore start --host-port="${EMULATOR_TARGET}" > "${LOG_FILE}" 2>&1 &
  EMULATOR_PID=$!
  echo "      Process launched (PID: ${EMULATOR_PID}, logs: ${LOG_FILE})."

  # Wait for emulator to be ready (up to 20 seconds)
  echo "      Waiting for emulator to accept connections..."
  READY=false
  for i in $(seq 1 20); do
    if curl -s --connect-timeout 1 "${EMULATOR_URL}/" 2>/dev/null | grep -q "Ok"; then
      READY=true
      break
    fi
    sleep 1
  done

  if [ "$READY" = true ]; then
    echo "      Emulator is ready!"
  else
    echo "[-] ERROR: Firestore emulator failed to start within 20s. Check logs:"
    cat "${LOG_FILE}"
    return 1 2>/dev/null || exit 1
  fi
fi

# 4. Export FIRESTORE_EMULATOR_HOST
export FIRESTORE_EMULATOR_HOST="${EMULATOR_TARGET}"
echo "[3/4] Exported FIRESTORE_EMULATOR_HOST=${FIRESTORE_EMULATOR_HOST}"

# 5. Idempotent Data Seeding
echo "[4/4] Seeding Firestore with initial dataset (idempotent upsert)..."
SEED_CMD=(uv run python -m tests.seed_data)
if [ -n "$BASE_DATE" ]; then
  SEED_CMD+=(--base-date "$BASE_DATE")
fi

FIRESTORE_EMULATOR_HOST="${EMULATOR_TARGET}" "${SEED_CMD[@]}"

echo "============================================================"
echo " [✓] Firestore Emulator ready and seeded successfully!"
echo "     Host: ${FIRESTORE_EMULATOR_HOST}"
echo "============================================================"

# Check if the script was sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo ""
  echo "NOTE: To retain FIRESTORE_EMULATOR_HOST in your current shell, run:"
  echo "      export FIRESTORE_EMULATOR_HOST=${EMULATOR_TARGET}"
  echo "      (or next time run: source $0)"
fi
