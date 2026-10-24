#!/usr/bin/env bash
# Run after nix build, not inside a derivation: activation registers real GC roots.
set -euo pipefail
dsh_environment=$(cd "$1" && pwd -P)
codex_environment=$(cd "$2" && pwd -P)
base=$(mktemp -d "${TMPDIR:-/tmp}/agent-env-dsh-delivery.XXXXXX")
base=$(cd "$base" && pwd -P)
export HOME="$base/home" CODEX_HOME="$base/home/.codex" TEST_DSH_PORT=18080
export project="$base/dsh-project" other_project="$base/codex-project"
mkdir -p "$HOME" "$project" "$other_project"
"$dsh_environment/bin/agent-env" apply --project "$project"
"$codex_environment/bin/agent-env" apply --project "$other_project"
python3 - "$dsh_environment" <<'PY'
import json, os, pathlib, sys, tomllib
project = pathlib.Path(os.environ['project'])
dsh = json.loads((project / '.dsh/mcp.json').read_text())['mcpServers']
codex = tomllib.loads((project / '.codex/config.toml').read_text())['mcp_servers']
assert dsh['remote']['type'] == 'http'
assert dsh['remote']['url'] == codex['remote']['url'] == 'http://127.0.0.1:18080/mcp'
assert dsh['fetch']['command'] == codex['fetch']['command']
assert dsh['fetch']['cwd'] == str(project)
assert not (pathlib.Path(os.environ['other_project']) / '.dsh/mcp.json').exists()
assert json.loads((pathlib.Path(sys.argv[1]) / 'manifest.json').read_text())['dshMcp'] is True
PY
"$dsh_environment/bin/agent-env" remove --project "$project"
python3 - <<'PY'
import json, os, pathlib
assert json.loads((pathlib.Path(os.environ['project']) / '.dsh/mcp.json').read_text())['mcpServers'] == {}
PY
"$codex_environment/bin/agent-env" remove --project "$other_project"
printf 'Verified DSH output, shared port, fixed command/cwd, default opt-out and owned cleanup. Outputs: %s\n' "$base"
