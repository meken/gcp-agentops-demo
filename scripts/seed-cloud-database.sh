#!/usr/bin/env bash
# ==============================================================================
# Seed Live Google Cloud Firestore Database for Cymbal Retail Agent
# ==============================================================================
# Usage:
#   ./scripts/seed-cloud-database.sh                          # Uses $GOOGLE_CLOUD_PROJECT
#   ./scripts/seed-cloud-database.sh --project my-gcp-project # Explicit project
#   ./scripts/seed-cloud-database.sh --database (default)     # Explicit database
#   ./scripts/seed-cloud-database.sh --yes                    # Non-interactive / CI
#   ./scripts/seed-cloud-database.sh --base-date 2026-08-18   # Fixed reference date
# ==============================================================================

set -e

# Default settings
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-${GCP_PROJECT:-}}"
DATABASE_ID="${FIRESTORE_DATABASE:-(default)}"
BASE_DATE=""
AUTO_CONFIRM=false

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --project)
      PROJECT_ID="$2"
      shift 2
      ;;
    --database)
      DATABASE_ID="$2"
      shift 2
      ;;
    --base-date)
      BASE_DATE="$2"
      shift 2
      ;;
    -y|--yes|--force)
      AUTO_CONFIRM=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--project PROJECT_ID] [--database DATABASE_ID] [--base-date YYYY-MM-DD] [--yes]"
      echo ""
      echo "Options:"
      echo "  --project PROJECT_ID    GCP Project ID (default: \$GOOGLE_CLOUD_PROJECT)"
      echo "  --database DATABASE_ID  Firestore Database ID (default: (default))"
      echo "  --base-date YYYY-MM-DD  Reference date for relative order dates (default: today)"
      echo "  -y, --yes, --force      Skip confirmation prompt"
      echo "  -h, --help              Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# If project is still not determined, try gcloud config
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
fi

# Validate project ID
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "[-] ERROR: No Google Cloud Project ID found."
  echo "    Please set GOOGLE_CLOUD_PROJECT environment variable or pass --project:"
  echo "      export GOOGLE_CLOUD_PROJECT=your-project-id"
  echo "      $0 --project your-project-id"
  exit 1
fi

echo "============================================================"
echo " Google Cloud Firestore Database Seeder"
echo " Project:  ${PROJECT_ID}"
echo " Database: ${DATABASE_ID}"
echo "============================================================"

# Guard: Inform if FIRESTORE_EMULATOR_HOST was set in the parent environment
if [ -n "$FIRESTORE_EMULATOR_HOST" ]; then
  echo "[i] NOTICE: FIRESTORE_EMULATOR_HOST=${FIRESTORE_EMULATOR_HOST} is currently set."
  echo "    Unsetting it for this execution to target the LIVE Google Cloud database."
fi

# Confirmation prompt for safety unless auto-confirmed
if [ "$AUTO_CONFIRM" = false ] && [ -t 0 ]; then
  echo ""
  read -r -p "Are you sure you want to seed the LIVE database in project '${PROJECT_ID}'? [y/N] " response
  case "$response" in
    [yY][eE][sS]|[yY])
      echo "Proceeding with seeding..."
      ;;
    *)
      echo "Seeding cancelled by user."
      exit 0
      ;;
  esac
fi

# Construct seed command arguments
SEED_ARGS=(--project "${PROJECT_ID}" --database "${DATABASE_ID}")
if [ -n "$BASE_DATE" ]; then
  SEED_ARGS+=(--base-date "$BASE_DATE")
fi

echo ""
echo "Connecting to Google Cloud Firestore and writing documents (idempotent)..."

# Execute seeding with FIRESTORE_EMULATOR_HOST explicitly unset
env -u FIRESTORE_EMULATOR_HOST GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" uv run python -m tests.seed_data "${SEED_ARGS[@]}"

echo ""
echo "============================================================"
echo " [✓] Google Cloud Firestore seeded successfully!"
echo "     Project:  ${PROJECT_ID}"
echo "     Database: ${DATABASE_ID}"
echo "============================================================"
