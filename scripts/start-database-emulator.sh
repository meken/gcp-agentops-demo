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
# NOTE: This script is designed to be sourced into an interactive shell.
#       Never use `set -e` / `set -u` at top level, as that mutates the caller's
#       shell options and can close the terminal on any error.

# Extract major Java version (e.g., "1.8.0_392" -> "8", "25.0.1" -> "25").
_sde_java_major_version() {
  local java_bin="$1"
  local version_output version_str

  if [ ! -x "${java_bin}" ]; then
    return 1
  fi

  version_output="$("${java_bin}" -version 2>&1)" || return 1
  version_str="$(printf '%s\n' "${version_output}" | sed -n 's/.*version "\([^"]*\)".*/\1/p' | head -n 1)"
  if [ -z "${version_str}" ]; then
    return 1
  fi

  case "${version_str}" in
    1.*)
      printf '%s\n' "${version_str}" | cut -d. -f2
      ;;
    *)
      printf '%s\n' "${version_str}" | sed 's/^\([0-9][0-9]*\).*/\1/'
      ;;
  esac
}

# Detect the minimum Java version required by the installed gcloud CLI.
# gcloud >= 590.0.0 requires Java 25; older versions required Java 21.
_sde_required_java_version() {
  local sdk_root="$1"
  local start_py="${sdk_root}/lib/surface/emulators/firestore/start.py"
  local detected=""

  if [ -n "${sdk_root}" ] && [ -r "${start_py}" ]; then
    detected="$(sed -n 's/.*RequireJavaInstalled([^)]*min_version=\([0-9][0-9]*\).*/\1/p' "${start_py}" | head -n 1)"
  fi

  if [[ "${detected}" =~ ^[0-9]+$ ]]; then
    printf '%s\n' "${detected}"
  else
    printf '25\n'
  fi
}

# Search common JVM installation locations for a Java runtime >= min_version.
# Prints the path to the java binary if found.
_sde_find_compatible_java() {
  local min_version="$1"
  local candidate major
  local -a candidates=()

  if [ -n "${JAVA_HOME:-}" ] && [ -x "${JAVA_HOME}/bin/java" ]; then
    candidates+=("${JAVA_HOME}/bin/java")
  fi

  # Common Linux, Cloud Shell, SDKMAN, and macOS Homebrew JVM paths
  local path
  for path in \
    /usr/lib/jvm/*/bin/java \
    "${HOME}/.sdkman/candidates/java/"*/bin/java \
    "${HOME}/.jdks/"*/bin/java \
    /opt/homebrew/opt/openjdk*/bin/java \
    /usr/local/opt/openjdk*/bin/java; do
    if [ -x "${path}" ]; then
      candidates+=("${path}")
    fi
  done

  for candidate in "${candidates[@]}"; do
    major="$(_sde_java_major_version "${candidate}" 2>/dev/null || true)"
    if [[ "${major}" =~ ^[0-9]+$ ]] && [ "${major}" -ge "${min_version}" ]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

_sde_print_usage() {
  local prog="$1"
  echo "Usage: [source] ${prog} [--host HOST] [--port PORT] [--host-port HOST:PORT] [--base-date YYYY-MM-DD]"
  echo ""
  echo "Options:"
  echo "  --host HOST         Host IP (default: 127.0.0.1)"
  echo "  --port PORT         Port number (default: 8888)"
  echo "  --host-port H:P     Combined host:port (default: 127.0.0.1:8888)"
  echo "  --base-date DATE    Reference date for order seeding (default: today)"
  echo "  -h, --help          Show this help message"
}

_sde_main() {
  local is_sourced="$1"
  shift

  local script_source="${BASH_SOURCE[0]:-$0}"
  local default_port="8888"
  local default_host="127.0.0.1"
  local host="${default_host}"
  local port="${default_port}"
  local base_date=""

  # Parse CLI arguments safely (never rely on set -e or unguarded shift 2)
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host)
        if [[ $# -lt 2 ]] || [ -z "${2}" ]; then
          echo "[-] ERROR: --host requires a value." >&2
          return 1
        fi
        host="$2"
        shift 2
        ;;
      --port)
        if [[ $# -lt 2 ]] || [ -z "${2}" ]; then
          echo "[-] ERROR: --port requires a value." >&2
          return 1
        fi
        port="$2"
        shift 2
        ;;
      --host-port)
        if [[ $# -lt 2 ]] || [[ "$2" != *:* ]]; then
          echo "[-] ERROR: --host-port requires a HOST:PORT value (e.g. 127.0.0.1:8888)." >&2
          return 1
        fi
        host="${2%:*}"
        port="${2##*:}"
        if [ -z "${host}" ] || [ -z "${port}" ]; then
          echo "[-] ERROR: Invalid --host-port value '$2'. Expected HOST:PORT." >&2
          return 1
        fi
        shift 2
        ;;
      --base-date)
        if [[ $# -lt 2 ]] || [ -z "${2}" ]; then
          echo "[-] ERROR: --base-date requires a YYYY-MM-DD value." >&2
          return 1
        fi
        base_date="$2"
        shift 2
        ;;
      -h|--help)
        _sde_print_usage "${script_source}"
        return 0
        ;;
      *)
        echo "[-] ERROR: Unknown option: $1" >&2
        _sde_print_usage "${script_source}" >&2
        return 1
        ;;
    esac
  done

  if ! [[ "${port}" =~ ^[0-9]+$ ]] || [ "${port}" -lt 1 ] || [ "${port}" -gt 65535 ]; then
    echo "[-] ERROR: Invalid port '${port}'. Must be an integer between 1 and 65535." >&2
    return 1
  fi

  local emulator_target="${host}:${port}"
  local emulator_url="http://${emulator_target}"

  echo "============================================================"
  echo " Start and Seed Firestore Emulator"
  echo " Target: ${emulator_target}"
  echo "============================================================"

  # 1. Locate Python virtual environment binary (active venv or local .venv)
  local script_dir repo_root python_bin
  script_dir="$(cd "$(dirname "${script_source}")" && pwd)" || {
    echo "[-] ERROR: Unable to determine script directory." >&2
    return 1
  }
  repo_root="$(cd "${script_dir}/.." && pwd)" || {
    echo "[-] ERROR: Unable to determine repository root." >&2
    return 1
  }

  if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    python_bin="${VIRTUAL_ENV}/bin/python"
  elif [ -x "${repo_root}/.venv/bin/python" ]; then
    python_bin="${repo_root}/.venv/bin/python"
  elif [ -x ".venv/bin/python" ]; then
    python_bin=".venv/bin/python"
  else
    echo "[-] ERROR: Python virtual environment not found." >&2
    echo "    Create one with 'uv sync --dev' or activate an existing venv:" >&2
    echo "      source .venv/bin/activate" >&2
    return 1
  fi

  # 2. Verify required CLI tools (gcloud, curl)
  if ! command -v gcloud >/dev/null 2>&1; then
    echo "[-] ERROR: Google Cloud CLI ('gcloud') was not found on PATH." >&2
    echo "    Install it from: https://cloud.google.com/sdk/docs/install" >&2
    return 1
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "[-] ERROR: 'curl' is required to check emulator readiness but was not found." >&2
    return 1
  fi

  local sdk_root
  sdk_root="$(gcloud info --format="value(installation.sdk_root)" 2>/dev/null || true)"
  if [ -z "${sdk_root}" ]; then
    echo "[-] ERROR: Could not determine Google Cloud SDK root via 'gcloud info'." >&2
    echo "    Verify your gcloud installation with: gcloud info" >&2
    return 1
  fi

  # 3. Verify Java Runtime version (gcloud >= 590.0.0 requires Java 25+)
  local min_java_version active_java_bin active_java_major
  local emulator_java_bin="" emulator_java_dir=""
  min_java_version="$(_sde_required_java_version "${sdk_root}")"

  active_java_bin="$(command -v java 2>/dev/null || true)"
  if [ -n "${active_java_bin}" ]; then
    active_java_major="$(_sde_java_major_version "${active_java_bin}" 2>/dev/null || true)"
  else
    active_java_major=""
  fi

  if [[ "${active_java_major}" =~ ^[0-9]+$ ]] && [ "${active_java_major}" -ge "${min_java_version}" ]; then
    emulator_java_bin="${active_java_bin}"
  else
    # Active java is missing or too old; look for a compatible JVM installed elsewhere
    local alt_java_bin alt_java_major
    alt_java_bin="$(_sde_find_compatible_java "${min_java_version}" 2>/dev/null || true)"
    if [ -n "${alt_java_bin}" ]; then
      alt_java_major="$(_sde_java_major_version "${alt_java_bin}" 2>/dev/null || true)"
      emulator_java_bin="${alt_java_bin}"
      emulator_java_dir="$(dirname "${alt_java_bin}")"
      echo "[i] Active java (${active_java_major:-none}) is below required Java ${min_java_version}."
      echo "    Using detected Java ${alt_java_major} at ${emulator_java_bin} for the emulator."
    else
      echo "[-] ERROR: Firestore emulator requires Java ${min_java_version}+ (Google Cloud CLI >= 590.0.0)." >&2
      if [ -n "${active_java_bin}" ]; then
        echo "    Found Java ${active_java_major:-unknown} at ${active_java_bin}, which is too old." >&2
      else
        echo "    No 'java' executable was found on PATH." >&2
      fi
      echo "" >&2
      echo "    Install Java ${min_java_version}+ using one of these options:" >&2
      echo "      - Debian 13+ / Ubuntu:" >&2
      echo "          sudo apt-get update && sudo apt-get install -y openjdk-${min_java_version}-jre-headless" >&2
      echo "      - Cloud Shell / persistent \$HOME install (via SDKMAN):" >&2
      echo "          curl -s \"https://get.sdkman.io\" | bash" >&2
      echo "          source \"\$HOME/.sdkman/bin/sdkman-init.sh\"" >&2
      echo "          sdk install java ${min_java_version}-tem" >&2
      echo "      - macOS (Homebrew):" >&2
      echo "          brew install openjdk@${min_java_version}" >&2
      return 1
    fi
  fi

  # 4. Check if Firestore emulator component is installed
  echo "[1/4] Checking Firestore emulator installation..."
  local emulator_jar="${sdk_root}/platform/cloud-firestore-emulator/cloud-firestore-emulator.jar"

  if [ ! -f "${emulator_jar}" ]; then
    echo "      Firestore emulator component not found. Attempting installation..."
    local install_success=false
    local install_log
    install_log="$(mktemp /tmp/firestore-emulator-install.XXXXXX.log 2>/dev/null || echo "/tmp/firestore-emulator-install-$$.log")"

    # Attempt 1: gcloud component manager (for standalone/tarball installations)
    if gcloud components install cloud-firestore-emulator --quiet >"${install_log}" 2>&1; then
      install_success=true
      echo "      Successfully installed cloud-firestore-emulator via gcloud."
    fi

    # Attempt 2: APT package manager (for Debian/Ubuntu/Cloud Shell APT-managed gcloud)
    if [ "${install_success}" = false ] && command -v apt-get >/dev/null 2>&1; then
      echo "      gcloud component manager unavailable. Attempting installation via apt..."
      if [ -n "${CLOUD_SHELL:-}" ]; then
        mkdir -p "${HOME}/.cloudshell" && touch "${HOME}/.cloudshell/no-apt-get-warning"
      fi
      if [ "$(id -u)" -eq 0 ]; then
        if apt-get update -qq >"${install_log}" 2>&1 && apt-get install -y -qq google-cloud-cli-firestore-emulator >>"${install_log}" 2>&1; then
          install_success=true
        fi
      elif command -v sudo >/dev/null 2>&1; then
        if sudo apt-get update -qq >"${install_log}" 2>&1 && sudo apt-get install -y -qq google-cloud-cli-firestore-emulator >>"${install_log}" 2>&1; then
          install_success=true
        fi
      fi
    fi

    # Attempt 3: DNF package manager (for RedHat/CentOS/Fedora)
    if [ "${install_success}" = false ] && command -v dnf >/dev/null 2>&1; then
      echo "      Attempting installation via dnf..."
      if [ "$(id -u)" -eq 0 ]; then
        if dnf install -y -q google-cloud-cli-firestore-emulator >"${install_log}" 2>&1; then
          install_success=true
        fi
      elif command -v sudo >/dev/null 2>&1; then
        if sudo dnf install -y -q google-cloud-cli-firestore-emulator >"${install_log}" 2>&1; then
          install_success=true
        fi
      fi
    fi

    # Verify if emulator is now present
    if [ ! -f "${emulator_jar}" ]; then
      echo "[-] ERROR: Failed to install the Firestore emulator component." >&2
      if [ -s "${install_log}" ]; then
        echo "    Last installer output:" >&2
        tail -n 20 "${install_log}" | sed 's/^/    | /' >&2
      fi
      rm -f "${install_log}"
      echo "" >&2
      echo "    Install it manually using your package manager:" >&2
      echo "      sudo apt-get install google-cloud-cli-firestore-emulator" >&2
      echo "    Or if using tarball gcloud:" >&2
      echo "      gcloud components install cloud-firestore-emulator" >&2
      return 1
    fi
    rm -f "${install_log}"
  else
    echo "      Firestore emulator component is installed."
  fi

  # 5. Check if emulator is already running on target host:port
  echo "[2/4] Checking if emulator is running at ${emulator_target}..."
  local is_running=false
  local probe_response=""
  if probe_response="$(curl -s --noproxy '*' --connect-timeout 2 "${emulator_url}/" 2>/dev/null)"; then
    if printf '%s' "${probe_response}" | grep -q "Ok"; then
      is_running=true
      echo "      Emulator is already running and responding at ${emulator_target}."
    elif [ -n "${probe_response}" ]; then
      echo "[-] ERROR: Another service is already listening on ${emulator_target} (unexpected response)." >&2
      echo "    Try starting on a different port: source ${script_source} --port 8889" >&2
      return 1
    fi
  fi

  local log_file="/tmp/firestore-emulator-${port}.log"
  if [ "${is_running}" = false ]; then
    echo "      Starting Firestore emulator in the background..."
    local emulator_pid
    if [ -n "${emulator_java_dir}" ]; then
      PATH="${emulator_java_dir}:${PATH}" JAVA="${emulator_java_bin}" \
        gcloud emulators firestore start --host-port="${emulator_target}" > "${log_file}" 2>&1 &
      emulator_pid=$!
    else
      gcloud emulators firestore start --host-port="${emulator_target}" > "${log_file}" 2>&1 &
      emulator_pid=$!
    fi
    echo "      Process launched (PID: ${emulator_pid}, logs: ${log_file})."

    # Wait for emulator to be ready (up to 25 seconds), failing fast if process exits
    echo "      Waiting for emulator to accept connections..."
    local ready=false
    local i emulator_exit_code
    for ((i = 1; i <= 25; i++)); do
      if curl -s --noproxy '*' --connect-timeout 1 "${emulator_url}/" 2>/dev/null | grep -q "Ok"; then
        ready=true
        break
      fi
      if ! kill -0 "${emulator_pid}" 2>/dev/null; then
        wait "${emulator_pid}" 2>/dev/null
        emulator_exit_code=$?
        echo "[-] ERROR: Firestore emulator process (PID ${emulator_pid}) exited prematurely (exit code: ${emulator_exit_code})." >&2
        if [ -s "${log_file}" ]; then
          echo "    Logs (${log_file}):" >&2
          sed 's/^/    | /' "${log_file}" >&2
        fi
        return 1
      fi
      sleep 1
    done

    if [ "${ready}" = true ]; then
      # Detach from interactive shell job control to avoid exit warnings
      disown "${emulator_pid}" 2>/dev/null || true
      echo "      Emulator is ready!"
    else
      echo "[-] ERROR: Firestore emulator failed to become ready within 25s." >&2
      if [ -s "${log_file}" ]; then
        echo "    Logs (${log_file}):" >&2
        sed 's/^/    | /' "${log_file}" >&2
      fi
      return 1
    fi
  fi

  # 6. Export FIRESTORE_EMULATOR_HOST
  export FIRESTORE_EMULATOR_HOST="${emulator_target}"
  echo "[3/4] Exported FIRESTORE_EMULATOR_HOST=${FIRESTORE_EMULATOR_HOST}"

  # 7. Idempotent Data Seeding
  echo "[4/4] Seeding Firestore with initial dataset (idempotent upsert)..."
  local -a seed_cmd=("${python_bin}" -m tests.seed_data)
  if [ -n "${base_date}" ]; then
    seed_cmd+=(--base-date "${base_date}")
  fi

  if ! (cd "${repo_root}" && FIRESTORE_EMULATOR_HOST="${emulator_target}" "${seed_cmd[@]}"); then
    echo "[-] ERROR: Failed to seed Firestore emulator at ${emulator_target}." >&2
    echo "    The emulator is running (logs: ${log_file}) and FIRESTORE_EMULATOR_HOST=${FIRESTORE_EMULATOR_HOST} is set." >&2
    echo "    Fix the error above and re-run seeding." >&2
    return 1
  fi

  echo "============================================================"
  echo " [✓] Firestore Emulator ready and seeded successfully!"
  echo "     Host: ${FIRESTORE_EMULATOR_HOST}"
  echo "============================================================"

  # Remind user if executed as a subshell rather than sourced
  if [ "${is_sourced}" -eq 0 ]; then
    echo ""
    echo "NOTE: To retain FIRESTORE_EMULATOR_HOST in your current shell, run:"
    echo "      export FIRESTORE_EMULATOR_HOST=${emulator_target}"
    echo "      (or next time run: source ${script_source})"
  fi

  return 0
}

# Detect whether the script was sourced or executed directly
_sde_is_sourced=0
if [ -n "${BASH_VERSION:-}" ]; then
  if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    _sde_is_sourced=1
  fi
elif [ -n "${ZSH_VERSION:-}" ]; then
  case "${ZSH_EVAL_CONTEXT:-}" in
    *:file|*:file:*) _sde_is_sourced=1 ;;
  esac
fi

_sde_rc=0
_sde_main "${_sde_is_sourced}" "$@" || _sde_rc=$?

# Clean up helper functions so sourcing does not pollute the caller's shell
unset -f _sde_java_major_version _sde_required_java_version _sde_find_compatible_java _sde_print_usage _sde_main

if [ "${_sde_is_sourced}" -eq 1 ]; then
  unset _sde_is_sourced
  return "${_sde_rc}"
fi
exit "${_sde_rc}"
