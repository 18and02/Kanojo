#!/usr/bin/env bash
set -euo pipefail

TIMEOUT="${TIMEOUT:-3}"
PYTHON_BIN="${PYTHON_BIN:-}"
PREFERRED_ROLE="${PREFERRED_ROLE:-mac_home}"

python_works() {
    local candidate="$1"
    command -v "$candidate" >/dev/null 2>&1 || return 1
    "$candidate" - <<'PY' >/dev/null 2>&1
import json
print("ok")
PY
}

if [[ -n "$PYTHON_BIN" ]]; then
    if ! python_works "$PYTHON_BIN"; then
        echo "PYTHON_BIN does not point to a working Python: $PYTHON_BIN" >&2
        exit 1
    fi
else
    for candidate in python3 python; do
        if python_works "$candidate"; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
    if [[ -z "$PYTHON_BIN" ]]; then
        echo "python3 or python is required" >&2
        exit 1
    fi
fi

if [[ "${1:-}" == "--role" ]]; then
    PREFERRED_ROLE="${2:-}"
    if [[ -z "$PREFERRED_ROLE" ]]; then
        echo "--role requires mac_home or pc_inference" >&2
        exit 1
    fi
    shift 2
fi

case "$PREFERRED_ROLE" in
    mac_home|pc_inference) ;;
    *)
        echo "PREFERRED_ROLE must be mac_home or pc_inference" >&2
        exit 1
        ;;
esac

if [[ "$#" -gt 0 ]]; then
    CANDIDATES=("$@")
else
    CANDIDATES=(
        "http://kanojo-mac.local:8787"
        "http://kanojo-mac-alt.local:8787"
        "http://kanojo-mac.local:8787"
        "http://kanojo-pc.local:8787"
        "http://kanojo-pc-alt.local:8787"
    )
fi

tmp_results="$(mktemp)"
trap 'rm -f "$tmp_results"' EXIT

index=0
for base in "${CANDIDATES[@]}"; do
    base="${base%/}"
    health=false
    status=false
    role=""
    node_name=""
    error=""
    if curl -fsS --max-time "$TIMEOUT" "$base/health" >/dev/null 2>&1; then
        health=true
        status_json="$(curl -fsS --max-time "$TIMEOUT" "$base/node/status" 2>/dev/null || true)"
        if [[ -n "$status_json" ]]; then
            status=true
            parsed="$(
                STATUS_JSON="$status_json" "$PYTHON_BIN" - <<'PY' 2>/dev/null || true
import json
import os

data = json.loads(os.environ.get("STATUS_JSON", "{}"))
node = data.get("node", {})
print(f"{node.get('role', '')}\t{node.get('name', '')}")
PY
            )"
            role="${parsed%%$'\t'*}"
            node_name="${parsed#*$'\t'}"
        fi
    else
        error="unreachable"
    fi

    INDEX="$index" \
    BASE_URL="$base" \
    HEALTH="$health" \
    STATUS="$status" \
    ROLE="$role" \
    NODE_NAME="$node_name" \
    ERROR="$error" \
    "$PYTHON_BIN" - <<'PY' >> "$tmp_results"
import json
import os

item = {
    "index": int(os.environ["INDEX"]),
    "base_url": os.environ["BASE_URL"],
    "health": os.environ["HEALTH"] == "true",
    "status": os.environ["STATUS"] == "true",
    "role": os.environ["ROLE"] or None,
    "node_name": os.environ["NODE_NAME"] or None,
    "error": os.environ["ERROR"] or None,
}
print(json.dumps(item, ensure_ascii=False))
PY
    index=$((index + 1))
done

"$PYTHON_BIN" - "$tmp_results" "$PREFERRED_ROLE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    results = [json.loads(line) for line in handle if line.strip()]

preferred_role = sys.argv[2]
role_order = ["pc_inference", "mac_home"] if preferred_role == "pc_inference" else ["mac_home", "pc_inference"]

def rank(item):
    if not (item.get("health") and item.get("status")):
        return (99, item.get("base_url") or "")
    role = item.get("role")
    try:
        return (role_order.index(role), item.get("index", 99))
    except ValueError:
        return (99, item.get("index", 99))

available = [item for item in results if item.get("health") and item.get("status")]
payload = {
    "preferred_role": preferred_role,
    "best": sorted(available, key=rank)[0] if available else None,
    "results": results,
}
json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
print()
PY
