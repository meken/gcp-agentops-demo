#!/usr/bin/env bash
# ==============================================================================
# Simulate Realistic Production Traffic for Cymbal Retail Agent
# ==============================================================================
# Generates realistic multi-turn customer conversations to simulate production
# traffic for the deployed Agent Engine. Traces and metrics are captured in
# Cloud Trace, Cloud Logging, and Vertex AI Online Evaluation.
#
# Usage:
#   ./scripts/simulate-traffic.sh
#   ./scripts/simulate-traffic.sh --sessions 20 --delay 1.5
#   ./scripts/simulate-traffic.sh --resource-name "projects/.../reasoningEngines/..."
# ==============================================================================

set -euo pipefail

# Default settings
RESOURCE_NAME="${AGENT_RESOURCE_NAME}"
LOCATION="${GOOGLE_CLOUD_LOCATION}"
TOTAL_SESSIONS=10
DELAY_BETWEEN_SESSIONS=2.0
DELAY_BETWEEN_TURNS=1.0

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --resource-name)
      RESOURCE_NAME="$2"
      shift 2
      ;;
    --location)
      LOCATION="$2"
      shift 2
      ;;
    --sessions)
      TOTAL_SESSIONS="$2"
      shift 2
      ;;
    --delay)
      DELAY_BETWEEN_SESSIONS="$2"
      shift 2
      ;;
    --turn-delay)
      DELAY_BETWEEN_TURNS="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --resource-name NAME   Agent Runtime Reasoning Engine resource name"
      echo "                         (default: \$AGENT_RESOURCE_NAME)"
      echo "  --location REGION      Google Cloud region (default: \$GOOGLE_CLOUD_LOCATION)"
      echo "  --sessions COUNT       Total conversation sessions to simulate (default: 10)"
      echo "  --delay SECONDS        Delay between sessions in seconds (default: 2.0)"
      echo "  --turn-delay SECONDS   Delay between conversation turns in seconds (default: 1.0)"
      echo "  -h, --help             Show this help message"
      exit 0
      ;;
    *)
      echo "[-] Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Validate prerequisites
if ! command -v curl &>/dev/null; then
  echo "[-] ERROR: curl is required but not installed." >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "[-] ERROR: jq is required but not installed." >&2
  exit 1
fi

if [ -z "$RESOURCE_NAME" ]; then
  echo "[-] ERROR: No resource name specified." >&2
  echo "    Set AGENT_RESOURCE_NAME or pass --resource-name" >&2
  exit 1
fi

# Obtain auth token
get_access_token() {
  local token
  token=$(gcloud auth print-access-token 2>/dev/null || true)
  if [ -z "$token" ]; then
    token=$(gcloud auth application-default print-access-token 2>/dev/null || true)
  fi
  if [ -z "$token" ]; then
    echo "[-] ERROR: Failed to obtain Google Cloud access token." >&2
    echo "    Please run 'gcloud auth login' or 'gcloud auth application-default login'." >&2
    exit 1
  fi
  echo "$token"
}

# Standard customer support scenarios
STANDARD_SCENARIOS_JSON='[
  {
    "name": "Order Status Inquiry",
    "turns": [
      "Hi, can you check the status of my order ORD-1001?",
      "When was it delivered and what items were in it?"
    ]
  },
  {
    "name": "In-Transit Order Inquiry",
    "turns": [
      "Where is my package for order ORD-1002?",
      "What is the estimated delivery date?"
    ]
  },
  {
    "name": "Inventory & Stock Check",
    "turns": [
      "Do you have the Wireless Noise Cancelling Headphones in stock?",
      "How many units are available and what is the price?"
    ]
  },
  {
    "name": "Stock Availability & Alternative",
    "turns": [
      "Is the Ultra Fitness Smartwatch in stock right now?",
      "What about mechanical keyboards?"
    ]
  },
  {
    "name": "Store Policy & Return Window",
    "turns": [
      "What is your return policy for electronics?",
      "Does my purchase come with a warranty?"
    ]
  },
  {
    "name": "Valid Refund Request",
    "turns": [
      "I would like to return order ORD-1001 because the headphones didn'\''t fit comfortably.",
      "Yes, please process a full refund of $199.99 for ORD-1001."
    ]
  },
  {
    "name": "In-Transit Delivery Inquiries",
    "turns": [
      "I want an update for order ORD-1002.",
      "Can you confirm the expected delivery timeline?"
    ]
  },
  {
    "name": "Already Refunded Order Check",
    "turns": [
      "Can you check if order ORD-1003 has been refunded yet?"
    ]
  }
]'

# Item and shipment inquiries
ITEM_INQUIRIES_JSON='[
  {
    "name": "Item Delivery Tracking",
    "turns": [
      "Please check the tracking and delivery status of my order ID SKU-HEADPHONES-01.",
      "Where is it currently located?"
    ]
  },
  {
    "name": "Package Delivery Inquiry",
    "turns": [
      "Can you look up my order SKU-KEYBOARD-02? I need to know when it will arrive.",
      "Which carrier is handling the shipment?"
    ]
  },
  {
    "name": "Order Dispatch Status",
    "turns": [
      "I placed an order yesterday for SKU-SMARTWATCH-04, can you check the order status for SKU-SMARTWATCH-04?",
      "Has the warehouse dispatched it yet?"
    ]
  },
  {
    "name": "Shipping Address & Package Status",
    "turns": [
      "Hi, can you check the delivery status of order ID SKU-MOUSE-03?",
      "Can you confirm the shipping address on file for that order?"
    ]
  },
  {
    "name": "Carrier Package Lookup",
    "turns": [
      "Where is the package for order SKU-HEADPHONES-01?",
      "What is the expected arrival date?"
    ]
  },
  {
    "name": "Order Delivery Confirmation",
    "turns": [
      "Could you look up order number SKU-KEYBOARD-02 and tell me if it has been delivered?",
      "Can you check the delivery timestamp?"
    ]
  }
]'

STANDARD_COUNT=$(echo "$STANDARD_SCENARIOS_JSON" | jq 'length')
INQUIRIES_COUNT=$(echo "$ITEM_INQUIRIES_JSON" | jq 'length')
ENDPOINT_URL="https://${LOCATION}-aiplatform.googleapis.com/v1/${RESOURCE_NAME}:streamQuery?alt=sse"

echo "============================================================"
echo " Starting Production Traffic Simulation"
echo " Target:        ${RESOURCE_NAME}"
echo " Location:      ${LOCATION}"
echo " Sessions:      ${TOTAL_SESSIONS}"
echo " Session Delay: ${DELAY_BETWEEN_SESSIONS}s"
echo " Turn Delay:    ${DELAY_BETWEEN_TURNS}s"
echo " Endpoint:      ${ENDPOINT_URL}"
echo "============================================================"
echo ""

ACCESS_TOKEN=$(get_access_token)

for ((session_idx=1; session_idx<=TOTAL_SESSIONS; session_idx++)); do
  # 50/50 balance between customer support scenarios
  if (( RANDOM % 2 == 0 )); then
    RAND_IDX=$(( RANDOM % STANDARD_COUNT ))
    SCENARIO_NAME=$(echo "$STANDARD_SCENARIOS_JSON" | jq -r ".[$RAND_IDX].name")
    TURN_COUNT=$(echo "$STANDARD_SCENARIOS_JSON" | jq ".[$RAND_IDX].turns | length")
    SELECTED_POOL="$STANDARD_SCENARIOS_JSON"
  else
    RAND_IDX=$(( RANDOM % INQUIRIES_COUNT ))
    SCENARIO_NAME=$(echo "$ITEM_INQUIRIES_JSON" | jq -r ".[$RAND_IDX].name")
    TURN_COUNT=$(echo "$ITEM_INQUIRIES_JSON" | jq ".[$RAND_IDX].turns | length")
    SELECTED_POOL="$ITEM_INQUIRIES_JSON"
  fi

  USER_ID="sim-user-$(( RANDOM % 9000 + 1000 ))"

  echo "[${session_idx}/${TOTAL_SESSIONS}] Starting Scenario: '${SCENARIO_NAME}' (User: ${USER_ID})"

  for ((t=0; t<TURN_COUNT; t++)); do
    TURN_NUM=$(( t + 1 ))
    USER_MESSAGE=$(echo "$SELECTED_POOL" | jq -r ".[$RAND_IDX].turns[$t]")
    echo "  [Turn ${TURN_NUM}] User:  ${USER_MESSAGE}"

    REQUEST_BODY=$(jq -n \
      --arg msg "$USER_MESSAGE" \
      --arg uid "$USER_ID" \
      '{classMethod: "stream_query", input: {message: $msg, user_id: $uid}}')

    # Query the deployed Agent Engine endpoint via curl
    RESPONSE=$(curl -s -N -X POST "$ENDPOINT_URL" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$REQUEST_BODY")

    # Check for HTTP or service errors
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.error.message // empty' 2>/dev/null | head -n 1)
    if [ -n "$ERROR_MSG" ]; then
      echo "  [Turn ${TURN_NUM}] Error: ${ERROR_MSG}" >&2
    else
      AGENT_TEXT=$(echo "$RESPONSE" | jq -r '.content.parts[]?.text // empty' 2>/dev/null | tr -d '\r' | paste -sd ' ' -)
      if [ -n "$AGENT_TEXT" ]; then
        if [ ${#AGENT_TEXT} -gt 140 ]; then
          DISPLAY_TEXT="${AGENT_TEXT:0:137}..."
        else
          DISPLAY_TEXT="$AGENT_TEXT"
        fi
        echo "  [Turn ${TURN_NUM}] Agent: ${DISPLAY_TEXT}"
      else
        echo "  [Turn ${TURN_NUM}] Agent: (No text generated)"
      fi
    fi

    # Pause between turns within the same conversation
    sleep "$DELAY_BETWEEN_TURNS"
  done

  echo "  [✓] Completed scenario '${SCENARIO_NAME}'."
  echo ""

  # Pause between sessions unless it is the last session
  if [ "$session_idx" -lt "$TOTAL_SESSIONS" ]; then
    sleep "$DELAY_BETWEEN_SESSIONS"
  fi
done

echo "============================================================"
echo " Traffic Simulation Completed! Production traces are captured in Cloud Trace."
echo " Check the Agent Platform Online Evaluation dashboard for live quality scores."
echo "============================================================"
