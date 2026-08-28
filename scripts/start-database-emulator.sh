#!/usr/bin/env bash
# ==============================================================================
# Setup, start, and seed Google Cloud Firestore Emulator for Cymbal Retail Agent
# ==============================================================================
# Usage:
#   source ./scripts/start-database-emulator.sh               # Starts, exports env, & seeds
#   ./scripts/start-database-emulator.sh                      # Runs as subshell and seeds
#   ./scripts/start-database-emulator.sh --port 8888          # Custom port
#   ./scripts/start-database-emulator.sh --base-date 2026-08-18 # Specific reference date
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
echo " Start and Seed Firestore Emulator"
echo " Target: ${EMULATOR_TARGET}"
echo "============================================================"

# 1. Locate Python virtual environment binary (active venv or local .venv)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
  PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
else
  echo "[-] ERROR: Python virtual environment not found."
  echo "    Please create a virtual environment (.venv) or activate an existing one:"
  echo "      source .venv/bin/activate"
  return 1 2>/dev/null || exit 1
fi

# 2. Verify Java Runtime (required by Firestore emulator)
if ! command -v java >/dev/null 2>&1; then
  echo "[-] ERROR: Java (JRE/JDK) is required to run the Firestore emulator but was not found."
  echo "    Please install Java: sudo apt-get install default-jre"
  return 1 2>/dev/null || exit 1
fi

# 2. Check if Firestore emulator component is installed
echo "[1/4] Checking Firestore emulator installation..."
SDK_ROOT=$(gcloud info --format="value(installation.sdk_root)" 2>/dev/null || echo "")
EMULATOR_JAR="${SDK_ROOT}/platform/cloud-firestore-emulator/cloud-firestore-emulator.jar"

if [ ! -f "${EMULATOR_JAR}" ]; then
  echo "      Firestore emulator component not found. Attempting installation..."

  # Attempt 1: gcloud component manager (for standalone/tarball installations)
  INSTALL_SUCCESS=false
  if gcloud components install cloud-firestore-emulator --quiet >/dev/null 2>&1; then
    INSTALL_SUCCESS=true
    echo "      Successfully installed cloud-firestore-emulator via gcloud."
  fi

  # Attempt 2: APT package manager (for Debian/Ubuntu/Cloud Shell APT-managed gcloud)
  if [ "$INSTALL_SUCCESS" = false ] && command -v apt-get >/dev/null 2>&1; then
    echo "      gcloud component manager is disabled. Attempting installation via apt..."
    if [ -n "${CLOUD_SHELL:-}" ]; then
      mkdir -p "${HOME}/.cloudshell" && touch "${HOME}/.cloudshell/no-apt-get-warning"
    fi
    if [ "$(id -u)" -eq 0 ]; then
      apt-get update -qq && apt-get install -y -qq google-cloud-cli-firestore-emulator && INSTALL_SUCCESS=true
    elif command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y -qq google-cloud-cli-firestore-emulator && INSTALL_SUCCESS=true
    fi
  fi

  # Attempt 3: YUM/DNF package manager (for RedHat/CentOS/Fedora)
  if [ "$INSTALL_SUCCESS" = false ] && command -v dnf >/dev/null 2>&1; then
    if [ "$(id -u)" -eq 0 ]; then
      dnf install -y -q google-cloud-cli-firestore-emulator && INSTALL_SUCCESS=true
    elif command -v sudo >/dev/null 2>&1; then
      sudo dnf install -y -q google-cloud-cli-firestore-emulator && INSTALL_SUCCESS=true
    fi
  fi

  # Verify if emulator is now present
  if [ ! -f "${EMULATOR_JAR}" ] && [ "$INSTALL_SUCCESS" = false ]; then
    echo "[-] ERROR: Failed to automatically install the Firestore emulator component."
    echo "    Please install it manually using your system package manager:"
    echo "      sudo apt-get install google-cloud-cli-firestore-emulator"
    echo "    Or if using tarball gcloud:"
    echo "      gcloud components install cloud-firestore-emulator"
    return 1 2>/dev/null || exit 1
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
SEED_CMD=("${PYTHON_BIN}" -m tests.seed_data)
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
