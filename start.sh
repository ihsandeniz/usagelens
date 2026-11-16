#!/usr/bin/env bash
# usage-tracker başlat — port 8770, loopback-only, stdlib Python (sıfır bağımlılık)
cd "$(dirname "$0")" || exit 1

# Provider API keys (optional) — same file the systemd service uses (EnvironmentFile=).
# Read as data, never run as shell code (SEC-F001): `. "$ENV_FILE"` executed `$(…)` and `;`
# inside a value. Only `NAME=value` lines count (optional `export `, one pair of matching
# quotes stripped, like systemd); anything else is skipped. `export "$k=$v"` expands nothing.
ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/usage-tracker/env"
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line#export }"
    [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    k="${BASH_REMATCH[1]}"; v="${BASH_REMATCH[2]}"
    if [[ "$v" =~ ^\"(.*)\"$ || "$v" =~ ^\'(.*)\'$ ]]; then v="${BASH_REMATCH[1]}"; fi
    export "$k=$v"
  done < "$ENV_FILE"
  unset line k v
fi

exec python3 server.py
