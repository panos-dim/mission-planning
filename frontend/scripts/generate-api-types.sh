#!/usr/bin/env bash
# Generate TypeScript types from the FastAPI OpenAPI schema.
#
# Usage:
#   npm run generate:api-types          # backend must be running on port 8000
#   OPENAPI_URL=http://host:port/openapi.json npm run generate:api-types
#
set -euo pipefail

OPENAPI_URL="${OPENAPI_URL:-http://localhost:8000/openapi.json}"
OUT_DIR="src/api/generated"
OUT_FILE="$OUT_DIR/api-types.ts"

mkdir -p "$OUT_DIR"

echo "⏳ Fetching OpenAPI schema from $OPENAPI_URL ..."

# Check if backend is reachable
if ! curl -sf "$OPENAPI_URL" > /dev/null 2>&1; then
  echo "❌ Cannot reach $OPENAPI_URL — is the backend running?"
  echo "   Start it with:  make dev  or  cd backend && uvicorn main:app --port 8000"
  exit 1
fi

npx openapi-typescript "$OPENAPI_URL" \
  --output "$OUT_FILE" \
  --root-types

echo "✅ Generated API types → $OUT_FILE"
