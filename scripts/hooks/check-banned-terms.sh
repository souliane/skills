#!/usr/bin/env bash
# Pre-commit hook: block commits containing banned terms.
#
# Usage: check-banned-terms.sh [--config PATH] FILE...
#
# Reads T3_BANNED_TERMS (comma-separated, case-insensitive) from the config
# file named by --config (default: ~/.teatree). Keeping the banned list OUTSIDE
# the repo avoids committing the very terms we want to keep out of it.
#
#   - config file missing        -> FAIL LOUD (exit 2): a leak gate that
#                                    silently passes is worse than no gate.
#   - config present, key unset  -> pass (exit 0): nothing configured to block.
#   - banned term found in files -> FAIL (exit 1).
set -euo pipefail

CONFIG="$HOME/.teatree"

# --- Parse args: pull out --config PATH; everything else is a file to scan. ---
FILES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)
      [ "$#" -ge 2 ] || { echo "check-banned-terms: --config needs a path" >&2; exit 2; }
      CONFIG="$2"
      shift 2
      ;;
    --config=*)
      CONFIG="${1#--config=}"
      shift
      ;;
    *)
      FILES+=("$1")
      shift
      ;;
  esac
done

# Expand a leading ~ (the shell does not expand it inside a quoted flag value).
case "$CONFIG" in
  "~") CONFIG="$HOME" ;;
  "~/"*) CONFIG="$HOME/${CONFIG#\~/}" ;;
esac

# Fail loud on a misconfigured gate rather than silently skipping the check.
if [ ! -f "$CONFIG" ]; then
  echo "check-banned-terms: config file not found: $CONFIG" >&2
  echo "Create it (with an optional T3_BANNED_TERMS=... line) or fix the" >&2
  echo "--config path in .pre-commit-config.yaml. Refusing to pass silently." >&2
  exit 2
fi

# Extract T3_BANNED_TERMS value (comma-separated).
# `|| true`: under `set -euo pipefail`, a no-match grep returns non-zero and would
# abort the whole hook before the empty-check below. A missing key must mean "nothing
# to check", not a hook crash.
TERMS=$(grep -E '^T3_BANNED_TERMS=' "$CONFIG" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
[ -n "$TERMS" ] || exit 0

# Build grep pattern: word-boundary match for each term.
PATTERN=""
IFS=',' read -ra TERM_ARRAY <<< "$TERMS"
for term in "${TERM_ARRAY[@]}"; do
  term=$(echo "$term" | xargs)  # trim whitespace
  [ -n "$term" ] || continue
  [ -n "$PATTERN" ] && PATTERN="$PATTERN|"
  PATTERN="$PATTERN\\b${term}\\b"
done
[ -n "$PATTERN" ] || exit 0

# Check staged files (guard the expansion so an empty list is safe under set -u).
FOUND=0
for file in ${FILES[@]+"${FILES[@]}"}; do
  [ -f "$file" ] || continue
  if grep -iEn "$PATTERN" "$file" 2>/dev/null; then
    echo "^^^ Banned term found in: $file"
    echo "These terms must not appear in this repo."
    echo "Configured in: $CONFIG (T3_BANNED_TERMS)"
    echo ""
    FOUND=1
  fi
done

exit "$FOUND"
