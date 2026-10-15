#!/usr/bin/env bash
set -euo pipefail
environment="$1"
base=$(mktemp -d "${TMPDIR:-/tmp}/agent-env-integration.XXXXXX")
export HOME="$base/home"
export CODEX_HOME="$HOME/.codex"
project="$base/project"
mkdir -p "$CODEX_HOME" "$project/.codex/agents" "$project/.agents/skills/keep" "$project/.agents/skills/example"
printf 'preexisting selected skill\n' > "$project/.agents/skills/example/SKILL.md"
printf 'obsolete selected content\n' > "$project/.agents/skills/example/stale.txt"
printf 'preexisting selected agent\n' > "$project/.codex/agents/example.toml"
printf 'unrelated skill\n' > "$project/.agents/skills/keep/SKILL.md"
cat > "$project/.codex/config.toml" <<'TOML'
# Keep this exact unrelated comment.
model = "example-existing-model"
[custom]
setting = "keep-me"
[mcp_servers.keep]
command = "/fixture/not-started"
TOML
"$environment/bin/agent-env" apply --project "$project"
test -f "$project/.agents/skills/example/SKILL.md"
test ! -e "$project/.agents/skills/example/stale.txt"
test -f "$project/.agents/skills/example/.example-data"
test -x "$project/.agents/skills/example/scripts/hello.sh"
test -f "$project/.codex/agents/example.toml"
test -z "$(find "$project/.agents/skills/example" "$project/.codex/agents" -type l -print -quit)"
"$project/.agents/skills/example/scripts/hello.sh"
grep -F '# Keep this exact unrelated comment.' "$project/.codex/config.toml"
grep -F 'keep-me' "$project/.codex/config.toml"
python3 - "$project" "$environment" <<'PY'
import json, pathlib, sys, tomllib
p=pathlib.Path(sys.argv[1])
x=tomllib.loads((p/'.codex/config.toml').read_text())
assert x['model']=='example-existing-model'
assert x['mcp_servers']['keep']['command']=='/fixture/not-started'
assert pathlib.Path(x['mcp_servers']['fetch']['command']).is_file()
role=tomllib.loads((p/'.codex/agents/example.toml').read_text())
assert role['name']=='example'
manifest=json.loads((pathlib.Path(sys.argv[2])/'manifest.json').read_text())
assert len(manifest['packages'])==2
assert (p/'.agent-env-nix/skills.list').read_text()=='example\n'
assert (p/'.agent-env-nix/agents.list').read_text()=='example\n'
roots=list((p/'.agent-env-nix/roots').iterdir())
assert len(roots)==1 and roots[0].is_symlink() and str(roots[0].readlink())==sys.argv[2]
print('Verified two packages, real copies, native agent, fixed MCP command, and root symlink.')
PY
nix-store --query --roots "$environment" | tee "$base/roots-before.txt"
grep -F "$project/.agent-env-nix/roots/" "$base/roots-before.txt"
printf '\nDirect generated edit, intentionally replaceable.\n' >> "$project/.agents/skills/example/SKILL.md"
printf 'edited selected agent\n' > "$project/.codex/agents/example.toml"
"$environment/bin/agent-env" apply --project "$project"
! grep -F 'edited selected agent' "$project/.codex/agents/example.toml"
! grep -F 'intentionally replaceable' "$project/.agents/skills/example/SKILL.md"
"$environment/bin/agent-env" remove --project "$project"
test ! -e "$project/.agents/skills/example"
test ! -e "$project/.codex/agents/example.toml"
test -f "$project/.agents/skills/keep/SKILL.md"
python3 - "$project" <<'PY'
import json, pathlib, sys, tomllib
p=pathlib.Path(sys.argv[1]); text=(p/'.codex/config.toml').read_text()
x=tomllib.loads(text)
assert x['model']=='example-existing-model'
assert x['custom']['setting']=='keep-me'
assert 'fetch' not in x['mcp_servers']
assert x['mcp_servers']['keep']['command']=='/fixture/not-started'
assert '# Keep this exact unrelated comment.' in text
s=json.loads((p/'.agent-env-nix/mcp-state.json').read_text())
assert s['mcp']=={}
assert (p/'.agent-env-nix/skills.list').read_text()==''
assert (p/'.agent-env-nix/agents.list').read_text()==''
assert list((p/'.agent-env-nix/roots').iterdir())==[]
print('Verified remove preserves unrelated config/skill and releases owned GC root.')
PY
printf 'INTEGRATION_PASS %s\n' "$base"

