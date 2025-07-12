#!/bin/bash

# Get the directory where the script itself resides
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Look for .env in the parent directory (arc-content-report root)
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

# Check required variables
if [ -z "$ORG_ID" ] || [ -z "$ENVIRONMENT" ] || [ -z "$BEARER_TOKEN" ]; then
  echo "ORG_ID, ENVIRONMENT and BEARER_TOKEN environment variables must be set in .env file."
  echo "Example .env file:"
  echo "ORG_ID=washpost"
  echo "ENVIRONMENT=sandbox"
  echo "BEARER_TOKEN=your_bearer_token_here"
  exit 1
fi

# Pass all arguments except org and token as EXTRA_ARGS
EXTRA_ARGS="$@"

# Run the published photo analysis script
python3 -m images_report.published_photo_analysis --org="$ORG_ID" --bearer-token="$BEARER_TOKEN" --environment="$ENVIRONMENT" $EXTRA_ARGS