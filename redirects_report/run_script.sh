#!/bin/bash

# Arc XP Redirects Report Script Runner
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

# Run the optimized script
python3 -m redirects_report.identify_redirects  \
  --org "$ORG_ID" \
  --bearer-token "$BEARER_TOKEN" \
  --website "$WEBSITE" \
  --website-domain "$WEBSITE_DOMAIN" \
  --output-prefix "$OUTPUT_PREFIX" \
  --environment "$ENVIRONMENT" \
  --do-404-or-200 "${DO_404_OR_200:-1}" \
  --max-workers "${MAX_WORKERS:-8}" \
  --auto-optimize-workers \
  --start-date "${DEFAULT_START_DATE:-}" \
  --end-date "${DEFAULT_END_DATE:-}" \
  "$@" 