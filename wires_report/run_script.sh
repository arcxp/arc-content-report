#!/bin/bash

# Arc XP Wires Report Script Runner
# Load credentials from .env file and run the optimized script

# Get the directory where the script itself resides
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Look for .env one directory above the script
ENV_FILE="${SCRIPT_DIR}/../.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found!"
    echo "Please copy config.env to .env and fill in your credentials:"
    echo "cp config.env .env"
    echo "Then edit .env with your actual API credentials"
    exit 1
fi

# Load environment variables
source $ENV_FILE

# Optionally set Q_EXTRA_FIELDS in your .env or environment to add ANS fields to _sourceInclude
# Example: export Q_EXTRA_FIELDS="distributor.name,source.system"
#   ${Q_EXTRA_FIELDS:+--q-extra-fields "$Q_EXTRA_FIELDS"} \

# Run the optimized script
python3 -m wires_report.identify_wires  \
  --org "$ORG_ID" \
  --bearer-token "$BEARER_TOKEN" \
  --website "$WEBSITE" \
  --environment "$ENVIRONMENT" \
  --max-workers "${MAX_WORKERS:-8}" \
  --start-date "${DEFAULT_START_DATE:-}" \
  --end-date "${DEFAULT_END_DATE:-}" \
  --output-prefix "${DEFAULT_WIRES_OUTPUT_PREFIX:-}" \
  --q-extra-filters "${Q_EXTRA_FILTERS:-}" \
  --q-extra-fields "${Q_EXTRA_FIELDS:-}" \
  "$@"