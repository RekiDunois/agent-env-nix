#!@bash@/bin/bash
set -euo pipefail

# Substituted by lib/cached-activation.nix; never resolve the installer or tools from PATH.
readonly environment='@environment@'
readonly coreutils='@coreutils@/bin'
fail() { printf '@name@: %s\n' "$*" >&2; exit 1; }

project=$PWD
force=false
while (( $# )); do
  case "$1" in
    --project)
      (( $# >= 2 )) && [[ -n $2 && $2 != --* ]] || fail '--project requires a directory'
      project=$2
      shift 2
      ;;
    --force) force=true; shift ;;
    --help)
      printf 'Usage: @name@ [--project DIRECTORY] [--force]\n'
      exit 0
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

# Resolve relative paths against the caller, never against inherited CDPATH.
[[ $project == /* ]] || project="$PWD/$project"
cd -P -- "$project" || fail "cannot enter project directory: $project"
project=$(pwd -P; printf '.')
project=${project%$'\n.'}
[[ $project != *$'\n'* ]] || fail 'project paths containing newlines are unsupported'
marker="$project/.agent-env-applied"
lock="$project/.agent-env-apply.lock"

# Serialize all wrapper versions for this project, including the cache check.
# Fail fast rather than wait forever on a lock left by an uncatchable crash.
"$coreutils/mkdir" -- "$lock" 2>/dev/null || fail "activation locked: $lock (if no activation is running, remove this directory and retry)"
cleanup() {
  "$coreutils/rm" -f -- "$lock/success"
  "$coreutils/rmdir" -- "$lock"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

[[ ! -L $marker && ( ! -e $marker || -f $marker ) ]] || fail "success marker must be a regular file: $marker"
# Resolve the same effective MCP values used by prepare, before any cache hit.
if ! mcp_key=$("$environment/bin/agent-env" cache-key); then
  "$coreutils/rm" -f -- "$marker"
  exit 1
fi
expected=$(printf 'v2\n%s\n%s\n%s' "$environment" "$project" "$mcp_key")
if [[ $force == false && -f $marker && $(<"$marker") == "$expected" ]]; then
  # These generated fragments are refreshed even when installation is cached.
  # Replace linked leaves rather than writing through them.
  for file in mcp-proxy.json mcp-connections.json; do
    "$coreutils/cp" --remove-destination -T -- "$environment/$file" "$project/$file"
    printf 'agent-env: exported %s (generated file; overwritten on activation).\n' "$project/$file"
  done
  exit 0
fi

# A failed repair/upgrade must not leave a previously valid success marker.
"$coreutils/rm" -f -- "$marker"
"$environment/bin/agent-env" apply --project "$project"
# The private lock directory is on the same filesystem: publish atomically.
printf '%s\n' "$expected" > "$lock/success"
"$coreutils/mv" -T -- "$lock/success" "$marker"

