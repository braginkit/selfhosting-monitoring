#!/usr/bin/env bash
set -euo pipefail

# Login Docker to GHCR using a GitHub App installation token.
#
# Required environment variables:
# - GH_APP_ID
# - GH_APP_INSTALLATION_ID
# - GH_APP_PRIVATE_KEY_PATH
#
# Optional environment variables:
# - GHCR_REGISTRY (default: ghcr.io)

GHCR_REGISTRY="${GHCR_REGISTRY:-ghcr.io}"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: $name" >&2
    exit 1
  fi
}

require_bin() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "Missing required command: $name" >&2
    exit 1
  fi
}

require_var "GH_APP_ID"
require_var "GH_APP_INSTALLATION_ID"
require_var "GH_APP_PRIVATE_KEY_PATH"

if [[ ! -f "$GH_APP_PRIVATE_KEY_PATH" ]]; then
  echo "Private key file not found: $GH_APP_PRIVATE_KEY_PATH" >&2
  exit 1
fi

require_bin "curl"
require_bin "openssl"
require_bin "python3"
require_bin "docker"

base64url() {
  openssl base64 -A | tr '+/' '-_' | tr -d '='
}

now="$(date +%s)"
iat="$((now - 60))"
exp="$((now + 540))"

header_b64="$(printf '{"alg":"RS256","typ":"JWT"}' | base64url)"
payload_b64="$(printf '{"iat":%s,"exp":%s,"iss":"%s"}' "$iat" "$exp" "$GH_APP_ID" | base64url)"
unsigned="${header_b64}.${payload_b64}"
signature_b64="$(printf '%s' "$unsigned" | openssl dgst -sha256 -sign "$GH_APP_PRIVATE_KEY_PATH" -binary | base64url)"
jwt="${unsigned}.${signature_b64}"

token_response="$(curl -fsSL \
  -X POST \
  -H "Authorization: Bearer ${jwt}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/app/installations/${GH_APP_INSTALLATION_ID}/access_tokens")"

install_token="$(
  printf '%s' "$token_response" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))'
)"

if [[ -z "$install_token" ]]; then
  echo "Failed to get installation token from GitHub App response" >&2
  exit 1
fi

printf '%s' "$install_token" | docker login "$GHCR_REGISTRY" -u x-access-token --password-stdin
echo "Docker login to ${GHCR_REGISTRY} succeeded via GitHub App."
