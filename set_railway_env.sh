#!/bin/bash
# Sync environment variables from agent/.env to Railway
# Usage: ./sync_env_to_railway.sh [path/to/.env]

ENV_FILE="${1:-agent/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: .env file not found at '$ENV_FILE'" >&2
    echo "Usage: $0 [path/to/.env]" >&2
    exit 1
fi

if ! command -v railway &> /dev/null; then
    echo "Error: railway CLI not found. Install it: npm install -g @railway/cli" >&2
    exit 1
fi

count=0
errors=0
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip comments and blank lines
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    key="${line%%=*}"
    value="${line#*=}"

    # Strip surrounding quotes from value
    value="${value#\"}"
    value="${value%\"}"
    value="${value#\'}"
    value="${value%\'}"

    # Skip lines without a key
    [[ -z "$key" ]] && continue

    echo -n "Setting $key... "
    if railway variables set "$key=$value" > /dev/null 2>&1; then
        echo "ok"
        ((count++))
    else
        echo "FAILED"
        ((errors++))
    fi
done < "$ENV_FILE"

echo "Done. Set $count variable(s), $errors failure(s) from $ENV_FILE"

